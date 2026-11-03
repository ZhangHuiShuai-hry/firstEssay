"""Immutable branch restrictions, explicit proof records and B&P numerical policy."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math


class RestrictionConflict(ValueError):
    pass


class NumericalUncertain(RuntimeError):
    pass


def coordinate_order(key):
    l, i, s, m = key
    return l, s, i, m


@dataclass(frozen=True)
class NumericPolicy:
    lp_primal_tolerance: float = 1e-8
    lp_dual_tolerance: float = 1e-8
    pricing_integrality_tolerance: float = 1e-7
    branch_integrality_tolerance: float = 1e-7
    column_local_tolerance: float = 1e-8
    reduced_cost_epsilon: float = 1e-7
    artificial_tolerance: float = 1e-7
    primal_validation_tolerance: float = 1e-6
    bound_consistency_tolerance: float = 1e-5
    global_absolute_tolerance: float = 1e-5
    global_relative_tolerance: float = 1e-8

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
                raise ValueError(f'{name} must be finite')
            if value < 0 or (value == 0 and name != 'global_relative_tolerance'):
                raise ValueError(f'{name} must be positive (relative tolerance may be zero)')
        if self.branch_integrality_tolerance >= .5 or self.pricing_integrality_tolerance >= .5:
            raise ValueError('Integrality tolerances must be less than 0.5')

    def allowance(self, lower):
        return max(self.global_absolute_tolerance,
                   self.global_relative_tolerance * max(1., abs(lower)))


@dataclass(frozen=True)
class NodeRestrictions:
    # Entries are (line, task, station, mode, value), never a shared mutable dict.
    fixes: tuple = ()

    def __post_init__(self):
        entries = tuple(tuple(entry) for entry in self.fixes)
        seen, selected = {}, {}
        for entry in entries:
            if len(entry) != 5:
                raise ValueError('Restriction must contain line, task, station, mode, value')
            l, i, s, m, b = entry
            if not all(isinstance(x, str) and x for x in (l, i, m)):
                raise ValueError('Invalid restriction identifier')
            if type(s) is not int or s < 1 or type(b) is not int or b not in (0, 1):
                raise ValueError('Invalid restriction station/value')
            q = l, i, s, m
            if q in seen:
                if seen[q] != b:
                    raise RestrictionConflict(f'Conflicting fixed variable {q}')
                raise ValueError(f'Duplicate fixed variable {q}')
            seen[q] = b
            if b:
                if (l, i) in selected:
                    raise RestrictionConflict(f'Task {(l,i)} fixed to one more than once')
                selected[l, i] = q
        object.__setattr__(self, 'fixes', tuple(sorted(entries, key=lambda e: coordinate_order(e[:4]))))

    def validate(self, data):
        lines = {l['id']: l for l in data['lines']}
        for l, i, s, m, b in self.fixes:
            if l not in lines or s > len(lines[l]['stations']):
                raise ValueError(f'Unknown line/station {(l,s)}')
            tasks = {t['id']: t for t in lines[l]['tasks']}
            if i not in tasks or m not in tasks[i]['modes']:
                raise ValueError(f'Unknown task/mode {(l,i,m)}')
        return self

    def add(self, data, key, value):
        return NodeRestrictions(self.fixes + (tuple(key) + (value,),)).validate(data)

    def is_child_of(self, parent):
        return len(self.fixes) == len(parent.fixes) + 1 and set(parent.fixes) < set(self.fixes)

    def allows(self, line_id, station, column):
        selected = set(column.assignments)
        return all(int((i, m) in selected) == b for l, i, s, m, b in self.fixes
                   if l == line_id and s == station)

    def block_fixes(self, line_id, station):
        return {(i, m): b for l, i, s, m, b in self.fixes if l == line_id and s == station}

    def to_records(self):
        return [{'variable': [l, i, s, m], 'value': b} for l, i, s, m, b in self.fixes]

    @classmethod
    def from_records(cls, data, records):
        if not isinstance(records, list):
            raise ValueError('Restriction records must be a list')
        return cls(tuple(tuple(e['variable']) + (e['value'],) for e in records)).validate(data)


@dataclass
class NodeCertificate:
    restrictions: list
    initialization: list = field(default_factory=list)
    initial_pool: list = field(default_factory=list)
    rounds: list = field(default_factory=list)
    phase1_status: str = 'not_run'
    phase2_status: str = 'not_run'
    solver_events: list = field(default_factory=list)
    error: dict | None = None


@dataclass
class NodeResult:
    status: str
    certificate: NodeCertificate
    pool: dict = field(default_factory=dict, repr=False)
    lp_objective: float | None = None
    lp_upper_bound: float | None = None
    lp_solution: list = field(default_factory=list)
    x_values: list = field(default_factory=list)
    columns_generated: int = 0
    pricing_calls: int = 0
    solve_seconds: float = 0.
    termination_reason: str = ''

    def to_dict(self):
        return {name: getattr(self, name) for name in (
            'status', 'lp_objective', 'lp_upper_bound', 'lp_solution', 'x_values',
            'columns_generated', 'pricing_calls', 'solve_seconds', 'termination_reason')}
        # Certificate is attached explicitly by the tree to avoid serializing pool keys.


@dataclass
class PricingCertificate:
    line: str
    station: int
    phase: int
    purpose: str
    fixed_variables: list = field(default_factory=list)
    status: str = 'solver_error'
    optimal: bool = False
    has_incumbent: bool = False
    incumbent: float | None = None
    reduced_cost: float | None = None
    objective: float | None = None
    best_bound: float | None = None
    assignments: list | None = None
    solve_seconds: float = 0.
    solver_result: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class NodePricingResult:
    certificate: PricingCertificate
    column: object | None = None


def pool_snapshot(pool):
    return [{'line': l, 'station': s, 'patterns': [list(c.assignments) for c in cols]}
            for (l, s), cols in sorted(pool.items())]


def most_fractional(x_values, restrictions, policy):
    fixed = {entry[:4] for entry in restrictions.fixes}
    candidates = []
    tol = policy.branch_integrality_tolerance
    for entry in x_values:
        q, value = tuple(entry['variable']), entry['value']
        if not math.isfinite(value) or value < -tol or value > 1 + tol:
            raise NumericalUncertain(f'Invalid recovered x {q}: {value}')
        if tol < value < 1 - tol:
            if q in fixed:
                raise NumericalUncertain('A fixed branch variable is fractional')
            candidates.append((abs(value - .5), coordinate_order(q), q, value))
    if not candidates:
        return None
    _, _, key, value = min(candidates)
    return {'variable': list(key), 'lp_value': value}

# FirstEssay

Research code for the ML-HRC-DLBP-CF disassembly line balancing study. It includes the compact MILP, Dantzig–Wolfe/column-generation implementation, CPLEX solver backend, experiment drivers and LaTeX formulation documents.

## Layout

- `code/milp/`: compact MILP and small example instances.
- `code/dwcg/`: master problem, exact pricing, CG-V2, and verification.
- `code/solver_backend.py`: CPLEX/CBC solver selection.
- `experiments/`: reproducible experiment scripts and protocols.
- `problem/`: mathematical formulation documents in LaTeX.

Experiment outputs, solver logs, virtual environments, and frozen run snapshots are excluded from this source repository.

See the README files in `code/milp`, `code/dwcg`, and `experiments` for setup and usage details.

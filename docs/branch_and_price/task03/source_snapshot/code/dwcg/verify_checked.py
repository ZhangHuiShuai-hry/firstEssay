"""Compatibility alias: use the current strict certificate verifier.

Kept for historical imports; there is one definition of verification semantics.
"""
from verify import cross_validate

__all__ = ["cross_validate"]

import sys
from pathlib import Path


def application_root():
    """Return the source root in development and the executable folder when frozen."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

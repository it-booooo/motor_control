"""Device interfaces and lazy backend factories.

Hardware-driver imports remain lazy so simulation/model tests do not require
python-can or pyserial to be importable.
"""

from .factory import create_motor_backend
from .motor_backend import BackendType, MotorBackend

__all__ = [
    "BackendType",
    "MotorBackend",
    "create_motor_backend",
]

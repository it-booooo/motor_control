"""Communication and actuator control concepts used across the application."""

from enum import Enum


class CommunicationType(str, Enum):
    """Physical/data-link communication used to reach an actuator."""

    CAN = "can"


class ControlMode(str, Enum):
    """Actuator firmware control modes, not communication protocols."""

    MIT = "mit"
    POSITION = "position"
    VELOCITY = "velocity"
    TORQUE = "torque"


CONTROL_MODE_LABELS = {
    ControlMode.MIT: "MIT Control Mode",
    ControlMode.POSITION: "Position Control Mode",
    ControlMode.VELOCITY: "Velocity Control Mode",
    ControlMode.TORQUE: "Torque Control Mode",
}

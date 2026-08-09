from dataclasses import dataclass

from ..controllers import ExperimentController, ManualControlController
from ..ui import ExperimentPanel, HardwarePanel, ManualControlPanel, TelemetryPanel, WorkspaceView


@dataclass
class ApplicationComponents:
    hardware_panel: HardwarePanel
    experiment_panel: ExperimentPanel
    manual_control_panel: ManualControlPanel
    telemetry_panel: TelemetryPanel
    workspace: WorkspaceView
    experiment_controller: ExperimentController
    manual_control_controller: ManualControlController


class ApplicationComposer:
    """Construct and wire the motor communication application."""

    def __init__(self, window, state):
        self.window = window
        self.state = state

    def compose(self):
        hardware_panel = HardwarePanel(self.state.hardware)
        experiment_panel = ExperimentPanel(self.state.hardware.safe_torque_max)
        manual_control_panel = ManualControlPanel()
        telemetry_panel = TelemetryPanel()
        workspace = WorkspaceView(hardware_panel, experiment_panel, manual_control_panel, telemetry_panel)
        experiment_controller = ExperimentController(
            parent=self.window, state=self.state, hardware_panel=hardware_panel,
            experiment_panel=experiment_panel, telemetry_panel=telemetry_panel,
        )
        manual_control_controller = ManualControlController(
            parent=self.window, state=self.state, hardware_panel=hardware_panel,
            manual_panel=manual_control_panel, telemetry_panel=telemetry_panel,
        )
        experiment_controller.set_background_busy_check(manual_control_controller.is_running)
        manual_control_controller.set_busy_check(experiment_controller.is_running)
        experiment_controller.running_changed.connect(
            lambda running: manual_control_panel.setEnabled(not running)
        )
        manual_control_controller.running_changed.connect(
            lambda running: experiment_panel.setEnabled(not running)
        )
        return ApplicationComponents(
            hardware_panel, experiment_panel, manual_control_panel, telemetry_panel, workspace,
            experiment_controller, manual_control_controller,
        )

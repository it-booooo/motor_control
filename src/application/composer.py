from dataclasses import dataclass

from ..controllers import AnalysisController, ExperimentController
from ..ui import (
    AnalysisPanel,
    ExperimentPanel,
    HardwarePanel,
    TelemetryPanel,
    WorkspaceView,
)


@dataclass
class ApplicationComponents:
    hardware_panel: HardwarePanel
    experiment_panel: ExperimentPanel
    telemetry_panel: TelemetryPanel
    analysis_panel: AnalysisPanel
    workspace: WorkspaceView
    experiment_controller: ExperimentController
    analysis_controller: AnalysisController


class ApplicationComposer:
    """Construct and wire the application's panels, workers, and controllers."""

    def __init__(self, window, state):
        self.window = window
        self.state = state

    def compose(self):
        hardware_panel = HardwarePanel(self.state.hardware)
        experiment_panel = ExperimentPanel(self.state.hardware.safe_torque_max)
        telemetry_panel = TelemetryPanel()
        analysis_panel = AnalysisPanel()
        workspace = WorkspaceView(
            hardware_panel,
            experiment_panel,
            telemetry_panel,
            analysis_panel,
        )
        analysis_controller = AnalysisController(parent=self.window, panel=analysis_panel)
        experiment_controller = ExperimentController(
            parent=self.window,
            state=self.state,
            hardware_panel=hardware_panel,
            experiment_panel=experiment_panel,
            telemetry_panel=telemetry_panel,
            log_panel=analysis_panel,
        )
        analysis_controller.set_measurement_busy_check(experiment_controller.is_running)
        experiment_controller.set_background_busy_check(analysis_controller.is_running)
        experiment_controller.running_changed.connect(
            lambda running: analysis_panel.setEnabled(not running)
        )
        analysis_controller.running_changed.connect(
            lambda running: hardware_panel.setEnabled(not running)
        )
        analysis_controller.running_changed.connect(
            lambda running: experiment_panel.setEnabled(not running)
        )

        def handle_measurement(path, auto_analyze):
            analysis_panel.set_file(path)
            if auto_analyze:
                analysis_controller.analyze(path)

        experiment_controller.measurement_completed.connect(handle_measurement)
        return ApplicationComponents(
            hardware_panel=hardware_panel,
            experiment_panel=experiment_panel,
            telemetry_panel=telemetry_panel,
            analysis_panel=analysis_panel,
            workspace=workspace,
            experiment_controller=experiment_controller,
            analysis_controller=analysis_controller,
        )

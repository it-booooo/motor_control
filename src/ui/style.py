APP_STYLE = """
QMainWindow, QWidget {
    background: #f3f5f7;
    color: #16202a;
    font-family: "Segoe UI", "Microsoft JhengHei";
    font-size: 10pt;
}
QMenuBar, QMenu { background: #ffffff; }
QMenuBar { border-bottom: 1px solid #d9e0e6; }
QMenuBar::item { padding: 6px 12px; }
QMenuBar::item:selected, QMenu::item:selected { background: #dbeafe; }
QGroupBox {
    background: #ffffff;
    border: 1px solid #d9e0e6;
    border-radius: 7px;
    font-weight: 600;
    margin-top: 11px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
    color: #334155;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit {
    background: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #bfdbfe;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border: 1px solid #2563eb;
}
QPushButton {
    background: #f8fafc;
    border: 1px solid #cbd5e1;
    border-radius: 4px;
    padding: 6px 10px;
}
QPushButton:hover { background: #eef2f7; }
QPushButton:pressed { background: #e2e8f0; }
QPushButton:disabled { color: #94a3b8; background: #f1f5f9; }
QPushButton#primaryButton {
    background: #2563eb;
    border-color: #1d4ed8;
    color: white;
    font-weight: 600;
}
QPushButton#primaryButton:hover { background: #1d4ed8; }
QPushButton#dangerButton {
    background: #dc2626;
    border-color: #b91c1c;
    color: white;
    font-weight: 700;
}
QPushButton#dangerButton:hover { background: #b91c1c; }
QProgressBar {
    background: #e2e8f0;
    border: 0;
    border-radius: 4px;
    text-align: center;
    min-height: 18px;
}
QProgressBar::chunk { background: #2563eb; border-radius: 4px; }
QTabWidget::pane { border: 1px solid #d9e0e6; background: #ffffff; }
QTabBar::tab { background: #e8edf2; padding: 7px 14px; }
QTabBar::tab:selected { background: #ffffff; color: #1d4ed8; }
QStatusBar { background: #ffffff; border-top: 1px solid #d9e0e6; }
QToolTip { background: #172033; color: white; border: 0; }
"""

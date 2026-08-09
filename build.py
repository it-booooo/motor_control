"""Build the motor communication GUI as one Windows executable."""

import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
APP_NAME = "MotorControl"
OUTPUT_EXE = ROOT / "dist" / f"{APP_NAME}.exe"


def conda_runtime_binaries():
    """Include DLLs that PyInstaller can miss in a Conda environment."""
    search_dirs = [Path(sys.prefix) / "Library" / "bin", Path(sys.prefix) / "DLLs"]
    patterns = (
        "ffi*.dll",
        "libffi*.dll",
        "expat*.dll",
        "libexpat*.dll",
        "sqlite3.dll",
        "libsqlite3*.dll",
    )
    arguments = []
    seen = set()
    separator = ";" if sys.platform == "win32" else ":"
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for pattern in patterns:
            for dll in sorted(directory.glob(pattern)):
                resolved = dll.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                arguments.extend(["--add-binary", f"{resolved}{separator}."])
    return arguments


def check_build_environment():
    modules = {"PyInstaller": "PyInstaller", "PySide6": "PySide6", "pyqtgraph": "pyqtgraph",
               "python-can": "can", "pyserial": "serial"}
    missing = [name for name, module in modules.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit("Missing build dependencies: " + ", ".join(missing))


def main():
    if sys.platform != "win32":
        raise SystemExit("build.py creates a Windows executable and must run on Windows.")
    check_build_environment()
    command = [
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--name", APP_NAME, "--windowed", "--onefile",
        "--collect-submodules=can.interfaces", "--collect-data=pyqtgraph",
        "--hidden-import=serial.tools.list_ports",
        *conda_runtime_binaries(),
        "__main__.py",
    ]
    subprocess.run(command, cwd=ROOT, check=True)
    if not OUTPUT_EXE.is_file() or OUTPUT_EXE.stat().st_size == 0:
        raise SystemExit(f"PyInstaller did not create {OUTPUT_EXE}")
    print(OUTPUT_EXE)


if __name__ == "__main__":
    main()

"""Build the Motor Control desktop GUI as a single Windows executable."""

import importlib
import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parent
ENV_ROOT = Path(sys.prefix)
APP_NAME = "MotorControl"
OUTPUT_EXE = ROOT / "dist" / f"{APP_NAME}.exe"


def ensure_output_is_replaceable():
    """Fail early with a useful message when the old EXE is still running."""
    if not OUTPUT_EXE.exists():
        return
    probe = OUTPUT_EXE.with_suffix(".exe.build-lock-check")
    try:
        OUTPUT_EXE.rename(probe)
        probe.rename(OUTPUT_EXE)
    except PermissionError as error:
        raise SystemExit(
            f"無法取代 {OUTPUT_EXE}。請關閉 MotorControl.exe（包含工作管理員中的背景程序）"
            "後再執行 build.py。"
        ) from error
    finally:
        if probe.exists() and not OUTPUT_EXE.exists():
            probe.rename(OUTPUT_EXE)


def conda_runtime_binaries():
    """Collect DLLs sometimes omitted from a Conda-based one-file bundle."""
    search_dirs = [ENV_ROOT / "Library" / "bin", ENV_ROOT / "DLLs"]
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
        if not directory.exists():
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
    modules = {
        "PyInstaller": "PyInstaller",
        "PySide6": "PySide6",
        "pyqtgraph": "pyqtgraph",
        "python-can": "can",
        "pyserial": "serial",
        "pandas": "pandas",
        "NumPy": "numpy",
        "Matplotlib": "matplotlib",
        "SciPy": "scipy",
    }
    missing = [name for name, module in modules.items() if importlib.util.find_spec(module) is None]
    if missing:
        raise SystemExit(
            "建置環境缺少："
            + ", ".join(missing)
            + f"。請先執行 `{sys.executable} -m pip install -r {ROOT / 'requirements.txt'}`。"
        )

    versions = []
    for name, module_name in modules.items():
        if name == "PyInstaller":
            continue
        try:
            module = importlib.import_module(module_name)
        except Exception as error:
            raise SystemExit(
                f"{name} 已安裝但無法載入：{type(error).__name__}: {error}"
            ) from error
        version = getattr(module, "__version__", "unknown")
        versions.append(f"  {name}: {version}")
    print("建置環境檢查完成：")
    print("\n".join(versions))


def main():
    if sys.platform != "win32":
        raise SystemExit("此 build.py 目前只產生 Windows .exe，請在 Windows 執行。")
    check_build_environment()
    ensure_output_is_replaceable()

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--clean",
        "--noconfirm",
        "--name",
        APP_NAME,
        "--windowed",
        "--onefile",
        "--collect-submodules=can.interfaces",
        "--collect-all=pyqtgraph",
        "--collect-data=matplotlib",
        "--hidden-import=serial.tools.list_ports",
        "--hidden-import=analyze",
        "--hidden-import=simulate",
        *conda_runtime_binaries(),
        "__main__.py",
    ]
    print("\n開始建立單一執行檔：")
    print(" ".join(str(part) for part in command))
    subprocess.run(command, cwd=ROOT, check=True)

    if not OUTPUT_EXE.is_file() or OUTPUT_EXE.stat().st_size == 0:
        raise SystemExit(f"PyInstaller 已結束，但找不到有效輸出：{OUTPUT_EXE}")
    print(f"\n建置完成：{OUTPUT_EXE}")
    print(f"檔案大小：{OUTPUT_EXE.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()

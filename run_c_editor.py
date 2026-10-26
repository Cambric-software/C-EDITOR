"""Start C EDITOR and install the desktop shortcut once."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent

if __name__ == "__main__":
    try:
        runpy.run_path(
            str(ROOT / "install_desktop_shortcut.py"),
            run_name="__shortcut_installer__")
    except Exception:
        pass
    runpy.run_path(
        str(ROOT / "c_editor.py"),
        run_name="__main__")

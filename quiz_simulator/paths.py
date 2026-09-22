import sys
from pathlib import Path


def app_root() -> Path:
    # I file persistenti restano accanto al programma per mantenerlo portatile.
    if getattr(sys, "frozen", False):
        directory = Path(sys.executable).resolve().parent
        project = directory.parent.parent
        if (
            directory.parent.name == "dist"
            and (project / "run_quiz.py").is_file()
            and (project / "pyproject.toml").is_file()
        ):
            return project
        return directory
    return Path(__file__).resolve().parent.parent


def resource(name: str) -> Path:
    bundled = Path(getattr(sys, "_MEIPASS", app_root())) / name
    local = app_root() / name
    return local if local.exists() else bundled

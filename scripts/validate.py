from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_VALIDATOR = Path.home() / ".codex" / "skills" / ".system" / "plugin-creator" / "scripts" / "validate_plugin.py"


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    run([sys.executable, "-m", "compileall", "src", "scripts", "tests"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    if PLUGIN_VALIDATOR.exists():
        run([sys.executable, str(PLUGIN_VALIDATOR), str(ROOT)])
    else:
        print(f"Skipping plugin validator; not found at {PLUGIN_VALIDATOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


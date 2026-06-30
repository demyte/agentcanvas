from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_VALIDATOR = Path.home() / ".codex" / "skills" / ".system" / "plugin-creator" / "scripts" / "validate_plugin.py"


def run(command: list[str]) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Canvas validation checks.")
    parser.add_argument("--installed", action="store_true", help="Also smoke-test the installed personal plugin cache.")
    parser.add_argument("--scenarios", action="store_true", help="Run the CLI/browser-surface scenario suite.")
    args = parser.parse_args()

    run([sys.executable, "-m", "compileall", "src", "scripts", "tests"])
    run([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    run([sys.executable, "scripts/smoke_cli.py", "--canvas-id", "validate-source-smoke"])
    if args.scenarios:
        run([sys.executable, "scripts/run_scenarios.py"])
    if args.installed:
        run([sys.executable, "scripts/smoke_cli.py", "--installed", "--canvas-id", "validate-installed-smoke"])
        if args.scenarios:
            run([sys.executable, "scripts/run_scenarios.py", "--installed"])
    if PLUGIN_VALIDATOR.exists():
        run([sys.executable, str(PLUGIN_VALIDATOR), str(ROOT)])
    else:
        print(f"Skipping plugin validator; not found at {PLUGIN_VALIDATOR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

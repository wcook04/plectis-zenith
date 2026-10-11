"""Install/remove the local macOS preview service; no public network listener."""
import argparse
import os
from pathlib import Path
import plistlib
import subprocess
import sys

LABEL = "com.plectis.observatory.preview"
ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "remove", "status"))
    parser.add_argument("--source-root", type=Path)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("Use python3 -m observatory.serve on non-macOS systems")
    domain = f"gui/{os.getuid()}"
    plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    if args.action == "status":
        return subprocess.run(["launchctl", "print", f"{domain}/{LABEL}"]).returncode
    if args.action == "remove":
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
        plist.unlink(missing_ok=True)
        print("Local preview service removed. Source files and research data retained.")
        return 0
    if args.source_root is not None and not args.source_root.is_dir():
        parser.error("The selected collector directory is unavailable")
    command = [sys.executable, "-m", "observatory.serve", "--host", "127.0.0.1", "--port", "8768"]
    if args.source_root:
        command += ["--source-root", str(args.source_root.resolve())]
    logs = Path.home() / "Library/Logs/PlectisObservatory"
    logs.mkdir(parents=True, exist_ok=True)
    payload = {"Label": LABEL, "ProgramArguments": command, "WorkingDirectory": str(ROOT),
               "RunAtLoad": True, "KeepAlive": {"SuccessfulExit": False}, "ThrottleInterval": 30,
               "StandardOutPath": str(logs / "preview.log"), "StandardErrorPath": str(logs / "preview-error.log")}
    plist.parent.mkdir(parents=True, exist_ok=True)
    if plist.exists():
        old = plistlib.loads(plist.read_bytes())
        if old.get("Label") != LABEL or old.get("WorkingDirectory") != str(ROOT):
            parser.error("An unrelated service occupies this name")
        subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    plist.write_bytes(plistlib.dumps(payload))
    result = subprocess.run(["launchctl", "bootstrap", domain, str(plist)])
    if result.returncode == 0:
        print("Local preview installed at http://127.0.0.1:8768 while logged in and awake.")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())

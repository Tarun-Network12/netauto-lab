#!/usr/bin/env python3
"""netauto: render, push, verify, back up and audit FRR configs with Nornir.

Usage:
    python3 automation/netauto.py render      # inventory + template -> rendered/
    python3 automation/netauto.py push        # push rendered config (merge only)
    python3 automation/netauto.py verify      # OSPF neighbors all Full?
    python3 automation/netauto.py apply       # render + push + verify
    python3 automation/netauto.py backup      # save running configs, commit to Git
    python3 automation/netauto.py drift       # running vs intended, exit 1 on drift
    python3 automation/netauto.py remediate   # fix drift, then re-check
    python3 automation/netauto.py compliance  # running configs vs compliance rules
    python3 automation/netauto.py validate    # inventory + rendered configs (no lab needed, used in CI)

Transport note: the lab routers are plain containers with no SSH daemon, so
commands go through `docker exec ... vtysh`. On real gear the transport tasks
would use SSH (Netmiko/NAPALM). Render, drift and verify logic stays the same.
"""
import argparse
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_utils.plugins.functions import print_result

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compliance import check_config, validate_inventory  # noqa: E402
from drift import compare  # noqa: E402
from render import render_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RENDERED = ROOT / "rendered"
BACKUPS = ROOT / "backups"
NOISE = "Can't open configuration file /etc/frr/vtysh.conf"


def _clean(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if NOISE not in l and l.strip())


def _vtysh(container: str, commands: list) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", container, "vtysh"]
    for c in commands:
        cmd += ["-c", c]
    return subprocess.run(cmd, capture_output=True, text=True)


def _errors(output: str) -> list:
    return [l for l in output.splitlines() if l.startswith("%") or "Unknown command" in l]


def _running(container: str) -> str:
    proc = _vtysh(container, ["show running-config"])
    out = _clean(proc.stdout + proc.stderr)
    if proc.returncode != 0 or not out:
        raise RuntimeError(f"could not read running-config from {container}: {out}")
    return out + "\n"


def _data(host) -> dict:
    return {k: host[k] for k in host.keys()}


def _intended(task: Task) -> str:
    return render_config(task.host.name, _data(task.host))


# --- tasks -----------------------------------------------------------------


def render_task(task: Task) -> Result:
    text = _intended(task)
    RENDERED.mkdir(exist_ok=True)
    (RENDERED / f"{task.host.name}.conf").write_text(text)
    return Result(host=task.host, result=f"rendered {len(text.splitlines())} lines")


def push_task(task: Task) -> Result:
    text = (RENDERED / f"{task.host.name}.conf").read_text()
    commands = ["configure terminal"]
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("!"):
            commands.append(line)
    proc = _vtysh(task.host.hostname, commands)
    out = _clean(proc.stdout + proc.stderr)
    failed = proc.returncode != 0 or bool(_errors(out))
    return Result(host=task.host, result=out or "pushed, no output", failed=failed)


def verify_task(task: Task) -> Result:
    proc = _vtysh(task.host.hostname, ["show ip ospf neighbor"])
    out = _clean(proc.stdout + proc.stderr)
    full = sum(1 for l in out.splitlines() if "Full/" in l)
    expected = len(task.host["interfaces"])
    msg = f"{full}/{expected} OSPF neighbors Full"
    return Result(host=task.host, result=msg, failed=(full != expected))


def backup_task(task: Task) -> Result:
    text = _running(task.host.hostname)
    BACKUPS.mkdir(exist_ok=True)
    path = BACKUPS / f"{task.host.name}.conf"
    previous = path.read_text() if path.exists() else None
    path.write_text(text)
    state = "new" if previous is None else ("changed" if previous != text else "unchanged")
    return Result(host=task.host, result=f"backup {state} ({len(text.splitlines())} lines)")


def drift_task(task: Task) -> Result:
    result = compare(_intended(task), _running(task.host.hostname))
    return Result(host=task.host, result=result.report(), failed=not result.clean)


def remediate_task(task: Task) -> Result:
    intended = _intended(task)
    before = compare(intended, _running(task.host.hostname))
    if before.clean:
        return Result(host=task.host, result="no drift, nothing to do")

    commands = before.commands()
    proc = _vtysh(task.host.hostname, commands)
    out = _clean(proc.stdout + proc.stderr)
    after = compare(intended, _running(task.host.hostname))

    lines = [before.report(), "applied:"] + [f"  {c}" for c in commands[1:]]
    lines.append("verified: no drift" if after.clean else "STILL DRIFTING:\n" + after.report())
    failed = proc.returncode != 0 or bool(_errors(out)) or not after.clean
    return Result(host=task.host, result="\n".join(lines), failed=failed)


def compliance_task(task: Task) -> Result:
    problems = check_config(task.host.name, _data(task.host), _running(task.host.hostname))
    msg = "compliant" if not problems else "NON-COMPLIANT\n" + "\n".join(f"  {p}" for p in problems)
    return Result(host=task.host, result=msg, failed=bool(problems))


def validate_task(task: Task) -> Result:
    """Offline: does the rendered config meet the rules? No devices touched."""
    problems = check_config(task.host.name, _data(task.host), _intended(task))
    msg = "rendered config compliant" if not problems else "\n".join(f"  {p}" for p in problems)
    return Result(host=task.host, result=msg, failed=bool(problems))


# --- git -------------------------------------------------------------------


def commit_backups() -> None:
    def git(*args, check=True):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=check)

    try:
        git("add", "backups")
        if git("diff", "--cached", "--quiet", "--", "backups", check=False).returncode == 0:
            print("\nNo config changes since the last backup. Nothing to commit.")
            return
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        git("commit", "-m", f"backup: running configs {stamp}", "--", "backups")
        print("\nCommitted config backup. See history with: make history")
    except subprocess.CalledProcessError as exc:
        print(f"\nBackup files written, but the Git commit failed:\n{exc.stderr}")


# --- cli -------------------------------------------------------------------

STEPS = {
    "render": [render_task],
    "push": [push_task],
    "verify": [verify_task],
    "apply": [render_task, push_task, verify_task],
    "backup": [backup_task],
    "drift": [drift_task],
    "remediate": [remediate_task],
    "compliance": [compliance_task],
    "validate": [validate_task],
}
INVENTORY_CHECKED = {"render", "apply", "validate"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=sorted(STEPS))
    args = parser.parse_args()

    nr = InitNornir(config_file=str(ROOT / "config.yaml"))

    if args.action in INVENTORY_CHECKED:
        errors = validate_inventory({h.name: _data(h) for h in nr.inventory.hosts.values()})
        if errors:
            print("\nInventory problems:")
            print("\n".join(f"  {e}" for e in errors))
            return 1
        print("\nInventory OK")

    any_failed = False
    for step in STEPS[args.action]:
        print(f"\n--- {step.__name__} ---")
        result = nr.run(task=step, name=step.__name__)
        print_result(result)
        any_failed = any_failed or result.failed
        if result.failed:
            break

    if args.action == "backup" and not any_failed:
        commit_backups()
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""netauto: render, push and verify FRR configs for the lab with Nornir.

Usage:
    python3 automation/netauto.py render
    python3 automation/netauto.py push
    python3 automation/netauto.py verify
    python3 automation/netauto.py apply     # render + push + verify

Transport note: the lab routers are plain containers with no SSH daemon, so
configs are pushed with `docker exec ... vtysh`. On real gear the push task
would use SSH (Netmiko/NAPALM). The render and verify logic stays the same.
"""
import argparse
import subprocess
import sys
from pathlib import Path

from nornir import InitNornir
from nornir.core.task import Result, Task
from nornir_utils.plugins.functions import print_result

sys.path.insert(0, str(Path(__file__).resolve().parent))
from render import render_config  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RENDERED = ROOT / "rendered"
NOISE = "Can't open configuration file /etc/frr/vtysh.conf"


def _clean(text: str) -> str:
    return "\n".join(l for l in text.splitlines() if NOISE not in l and l.strip())


def _vtysh(container: str, commands: list) -> subprocess.CompletedProcess:
    cmd = ["docker", "exec", container, "vtysh"]
    for c in commands:
        cmd += ["-c", c]
    return subprocess.run(cmd, capture_output=True, text=True)


def render_task(task: Task) -> Result:
    data = {k: task.host[k] for k in task.host.keys()}
    text = render_config(task.host.name, data)
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
    errors = [l for l in out.splitlines() if l.startswith("%") or "Unknown command" in l]
    failed = proc.returncode != 0 or bool(errors)
    return Result(host=task.host, result=out or "pushed, no output", failed=failed)


def verify_task(task: Task) -> Result:
    proc = _vtysh(task.host.hostname, ["show ip ospf neighbor"])
    out = _clean(proc.stdout + proc.stderr)
    full = sum(1 for l in out.splitlines() if "Full/" in l)
    expected = len(task.host["interfaces"])
    msg = f"{full}/{expected} OSPF neighbors Full"
    return Result(host=task.host, result=msg, failed=(full != expected))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("action", choices=["render", "push", "verify", "apply"])
    args = parser.parse_args()

    nr = InitNornir(config_file=str(ROOT / "config.yaml"))
    steps = {
        "render": [render_task],
        "push": [push_task],
        "verify": [verify_task],
        "apply": [render_task, push_task, verify_task],
    }[args.action]

    any_failed = False
    for step in steps:
        print(f"\n--- {step.__name__} ---")
        result = nr.run(task=step, name=step.__name__)
        print_result(result)
        any_failed = any_failed or result.failed
        if result.failed:
            break
    return 1 if any_failed else 0


if __name__ == "__main__":
    sys.exit(main())

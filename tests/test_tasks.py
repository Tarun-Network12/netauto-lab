"""Task-level tests with a fake device, so no containers are needed."""
import subprocess
from pathlib import Path

import pytest
from nornir import InitNornir

import automation.netauto as netauto

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"


@pytest.fixture
def nr():
    return InitNornir(config_file=str(ROOT / "config.yaml"), logging={"enabled": False})


class FakeFabric:
    """r1 starts drifted (cost 50). Others match intent."""

    def __init__(self, drifted=True):
        self.r1 = (FIX / ("r1_running_cost50.txt" if drifted else "r1_running.txt")).read_text()
        self.applied = []

    def vtysh(self, container, commands):
        if commands == ["show running-config"]:
            out = self.r1 if container.endswith("r1") else self._rendered(container)
        else:
            self.applied.append((container, commands))
            if container.endswith("r1") and "no ip ospf cost 50" in commands:
                self.r1 = (FIX / "r1_running.txt").read_text()
            out = ""
        return subprocess.CompletedProcess([], 0, stdout=out, stderr="")

    @staticmethod
    def _rendered(container):
        import yaml
        from automation.render import render_config
        name = container.split("-")[-1]
        hosts = yaml.safe_load((ROOT / "inventory" / "hosts.yaml").read_text())
        defaults = yaml.safe_load((ROOT / "inventory" / "defaults.yaml").read_text())["data"]
        return render_config(name, {**defaults, **hosts[name]["data"]})


def _results(nr, task):
    res = nr.run(task=task)
    return res, {h: r[0] for h, r in res.items()}


def test_drift_task_flags_only_the_drifted_router(nr, monkeypatch):
    monkeypatch.setattr(netauto, "_vtysh", FakeFabric().vtysh)
    res, per = _results(nr, netauto.drift_task)
    assert per["r1"].failed and "ip ospf cost 50" in per["r1"].result
    assert not per["r2"].failed and not per["r3"].failed


def test_remediate_task_fixes_and_verifies(nr, monkeypatch):
    fab = FakeFabric()
    monkeypatch.setattr(netauto, "_vtysh", fab.vtysh)
    res, per = _results(nr, netauto.remediate_task)
    assert not res.failed
    assert "verified: no drift" in per["r1"].result
    assert "no drift, nothing to do" in per["r2"].result
    assert len(fab.applied) == 1


def test_clean_state_has_no_failures(nr, monkeypatch):
    monkeypatch.setattr(netauto, "_vtysh", FakeFabric(drifted=False).vtysh)
    res, _ = _results(nr, netauto.drift_task)
    assert not res.failed


def test_backup_task_writes_files(nr, monkeypatch, tmp_path):
    monkeypatch.setattr(netauto, "_vtysh", FakeFabric().vtysh)
    monkeypatch.setattr(netauto, "BACKUPS", tmp_path)
    res, per = _results(nr, netauto.backup_task)
    assert not res.failed
    assert {p.name for p in tmp_path.iterdir()} == {"r1.conf", "r2.conf", "r3.conf"}
    assert "new" in per["r1"].result
    res2, per2 = _results(nr, netauto.backup_task)
    assert "unchanged" in per2["r1"].result

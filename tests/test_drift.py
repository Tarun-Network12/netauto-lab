"""Drift logic tests. Uses real `show running-config` output captured from the lab."""
from pathlib import Path

import yaml

from automation.drift import compare, parse_config
from automation.render import render_config

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
HOSTS = yaml.safe_load((ROOT / "inventory" / "hosts.yaml").read_text())
DEFAULTS = yaml.safe_load((ROOT / "inventory" / "defaults.yaml").read_text())["data"]


def intended(name="r1"):
    return render_config(name, {**DEFAULTS, **HOSTS[name]["data"]})


def test_clean_device_has_no_drift():
    d = compare(intended(), (FIX / "r1_running.txt").read_text())
    assert d.clean
    assert d.report() == "no drift"


def test_unexpected_line_is_detected_and_removed():
    d = compare(intended(), (FIX / "r1_running_cost50.txt").read_text())
    assert d.extra == {"interface eth2": ["ip ospf cost 50"]}
    assert not d.missing
    assert d.commands() == ["configure terminal", "interface eth2", "no ip ospf cost 50"]
    assert "unexpected on device: ip ospf cost 50" in d.report()


def test_missing_line_is_detected_and_added():
    running = (FIX / "r1_running.txt").read_text().replace(" network 10.0.13.0/30 area 0\n", "")
    d = compare(intended(), running)
    assert d.missing == {"router ospf": ["network 10.0.13.0/30 area 0"]}
    assert d.commands() == ["configure terminal", "router ospf", "network 10.0.13.0/30 area 0"]


def test_unexpected_router_block_becomes_stale_context():
    running = (FIX / "r1_running.txt").read_text().replace(
        "end\n", "router bgp 65001\n bgp router-id 1.1.1.1\nexit\n!\nend\n"
    )
    d = compare(intended(), running)
    assert d.stale_contexts == ["router bgp 65001"]
    assert "no router bgp 65001" in d.commands()


def test_platform_noise_is_ignored():
    assert parse_config("frr version 8.4.1_git\nno ipv6 forwarding\n")["global"] == set()


def test_removals_come_before_additions():
    running = (FIX / "r1_running_cost50.txt").read_text().replace(" network 10.0.13.0/30 area 0\n", "")
    cmds = compare(intended(), running).commands()
    assert cmds.index("no ip ospf cost 50") < cmds.index("network 10.0.13.0/30 area 0")

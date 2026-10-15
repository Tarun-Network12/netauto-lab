import copy
from pathlib import Path

import pytest
import yaml

import automation.netauto as netauto
from automation.compliance import check_config, validate_inventory
from automation.render import render_config

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures"
HOSTS = yaml.safe_load((ROOT / "inventory" / "hosts.yaml").read_text())
DEFAULTS = yaml.safe_load((ROOT / "inventory" / "defaults.yaml").read_text())["data"]


def inv():
    return copy.deepcopy({n: {**DEFAULTS, **h["data"]} for n, h in HOSTS.items()})


# --- inventory ---

def test_real_inventory_is_valid():
    assert validate_inventory(inv()) == []


def test_duplicate_interface_name_is_rejected():
    data = inv()
    data["r1"]["interfaces"].append(dict(data["r1"]["interfaces"][0]))
    errors = validate_inventory(data)
    assert any("duplicate interface name eth1" in e for e in errors)


def test_duplicate_ip_is_rejected():
    data = inv()
    data["r2"]["interfaces"][0]["ip"] = "10.0.12.1/30"
    assert any("already used by r1 eth1" in e for e in validate_inventory(data))


def test_router_id_must_match_loopback():
    data = inv()
    data["r3"]["router_id"] = "9.9.9.9"
    assert any("does not match loopback" in e for e in validate_inventory(data))


def test_link_with_one_end_is_rejected():
    data = inv()
    data["r3"]["interfaces"][1]["ip"] = "10.0.99.2/30"
    assert any("expected exactly 2 routers" in e for e in validate_inventory(data))


def test_invalid_address_is_reported_not_crashed():
    data = inv()
    data["r1"]["interfaces"][0]["ip"] = "10.0.12.999/30"
    assert any("invalid address" in e for e in validate_inventory(data))


# --- config rules ---

@pytest.mark.parametrize("name", sorted(HOSTS))
def test_rendered_configs_are_compliant(name):
    data = inv()[name]
    assert check_config(name, data, render_config(name, data)) == []


def test_real_running_config_is_compliant():
    assert check_config("r1", inv()["r1"], (FIX / "r1_running.txt").read_text()) == []


def test_missing_network_statement_is_flagged():
    text = (FIX / "r1_running.txt").read_text().replace(" network 10.0.13.0/30 area 0\n", "")
    assert any(p.startswith("C6") for p in check_config("r1", inv()["r1"], text))


def test_wrong_router_id_is_flagged():
    text = (FIX / "r1_running.txt").read_text().replace("router-id 1.1.1.1", "router-id 7.7.7.7")
    assert any(p.startswith("C2") for p in check_config("r1", inv()["r1"], text))


def test_unapproved_protocol_is_flagged():
    text = (FIX / "r1_running.txt").read_text().replace(
        "end\n", "router bgp 65001\n bgp router-id 1.1.1.1\nexit\n!\nend\n")
    assert any("C7" in p and "router bgp 65001" in p for p in check_config("r1", inv()["r1"], text))


def test_wrong_hostname_is_flagged():
    text = (FIX / "r1_running.txt").read_text().replace("hostname r1", "hostname rX")
    assert any(p.startswith("C1") for p in check_config("r1", inv()["r1"], text))


# --- task wiring ---

def test_compliance_task_fails_on_bad_device(monkeypatch):
    from nornir import InitNornir
    nr = InitNornir(config_file=str(ROOT / "config.yaml"), logging={"enabled": False})

    def fake_running(container):
        name = container.split("-")[-1]
        text = render_config(name, inv()[name])
        return text.replace("router-id 1.1.1.1", "router-id 7.7.7.7") if name == "r1" else text

    monkeypatch.setattr(netauto, "_running", fake_running)
    res = nr.run(task=netauto.compliance_task)
    assert res["r1"][0].failed and "C2" in res["r1"][0].result
    assert not res["r2"][0].failed and not res["r3"][0].failed

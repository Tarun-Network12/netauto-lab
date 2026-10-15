"""Golden-config tests: the template must reproduce the known-good configs."""
from pathlib import Path

import pytest
import yaml
from jinja2.exceptions import UndefinedError

from automation.render import render_config

ROOT = Path(__file__).resolve().parent.parent
HOSTS = yaml.safe_load((ROOT / "inventory" / "hosts.yaml").read_text())
DEFAULTS = yaml.safe_load((ROOT / "inventory" / "defaults.yaml").read_text())["data"]


def _data(name: str) -> dict:
    return {**DEFAULTS, **HOSTS[name]["data"]}


@pytest.mark.parametrize("name", sorted(HOSTS))
def test_render_matches_golden_config(name):
    golden = (ROOT / "topology" / "configs" / f"{name}.conf").read_text()
    assert render_config(name, _data(name)) == golden


def test_ospf_cost_is_rendered_when_set():
    data = _data("r1")
    data["interfaces"] = [dict(i) for i in data["interfaces"]]
    data["interfaces"][1]["ospf_cost"] = 50
    out = render_config("r1", data)
    assert " ip ospf cost 50" in out


def test_no_cost_line_by_default():
    assert "ospf cost" not in render_config("r1", _data("r1"))


def test_missing_variable_fails_loudly():
    data = _data("r1")
    del data["router_id"]
    with pytest.raises(UndefinedError):
        render_config("r1", data)

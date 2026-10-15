"""Pure rendering logic: inventory data in, FRR config text out.

Kept free of Nornir and Docker so it can be unit tested anywhere.
"""
import ipaddress
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATES = Path(__file__).resolve().parent.parent / "templates"


def _network(cidr: str) -> str:
    """10.0.12.1/30 -> 10.0.12.0/30"""
    return str(ipaddress.ip_interface(cidr).network)


def _env() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,  # a missing variable is an error, not a blank
    )
    env.filters["network"] = _network
    return env


def render_config(hostname: str, data: dict) -> str:
    data = {k: v for k, v in data.items() if k != "hostname"}
    return _env().get_template("frr.conf.j2").render(hostname=hostname, **data)

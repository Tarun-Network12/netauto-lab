"""Compliance rules. Pure logic, no devices needed.

Two layers:
  validate_inventory(hosts)  -> problems in the source of truth itself
  check_config(name, data, text) -> problems in a config (rendered or running)

Both return a list of strings. Empty list means compliant.
"""
import ipaddress
from collections import defaultdict

from drift import parse_config


def _iface(cidr):
    try:
        return ipaddress.ip_interface(cidr)
    except ValueError:
        return None


def validate_inventory(hosts: dict) -> list:
    """hosts: {name: data}. Catches mistakes before they reach a router."""
    errors = []
    ip_owner = {}
    subnet_members = defaultdict(list)
    router_ids = {}

    for name in sorted(hosts):
        data = hosts[name]
        names = [i["name"] for i in data["interfaces"]]
        for dup in sorted({n for n in names if names.count(n) > 1}):
            errors.append(f"{name}: duplicate interface name {dup}")

        addrs = [("lo", data["loopback"])] + [(i["name"], i["ip"]) for i in data["interfaces"]]
        for ifname, cidr in addrs:
            parsed = _iface(cidr)
            if parsed is None:
                errors.append(f"{name} {ifname}: invalid address {cidr}")
                continue
            key = str(parsed.ip)
            if key in ip_owner:
                errors.append(f"{name} {ifname}: IP {key} already used by {ip_owner[key]}")
            else:
                ip_owner[key] = f"{name} {ifname}"
            if ifname != "lo":
                subnet_members[str(parsed.network)].append(name)

        lo = _iface(data["loopback"])
        if lo is not None and str(lo.ip) != str(data["router_id"]):
            errors.append(f"{name}: router_id {data['router_id']} does not match loopback {lo.ip}")
        if lo is not None and lo.network.prefixlen != 32:
            errors.append(f"{name}: loopback should be a /32, got {data['loopback']}")
        rid = str(data["router_id"])
        if rid in router_ids:
            errors.append(f"{name}: router_id {rid} already used by {router_ids[rid]}")
        router_ids[rid] = name

    for net, members in sorted(subnet_members.items()):
        if len(members) != 2 or len(set(members)) != 2:
            errors.append(f"link {net}: expected exactly 2 routers, found {sorted(members)}")
    return errors


def check_config(name: str, data: dict, text: str) -> list:
    """Rules every router config must meet."""
    cfg = parse_config(text)
    glob = cfg.get("global", set())
    ospf = cfg.get("router ospf", set())
    area = data.get("ospf_area", 0)
    problems = []

    if f"hostname {name}" not in glob:
        problems.append(f"C1 hostname is not {name}")
    if f"ospf router-id {data['router_id']}" not in ospf:
        problems.append(f"C2 OSPF router-id is not {data['router_id']}")

    lo = _iface(data["loopback"])
    if f"ip address {data['loopback']}" not in cfg.get("interface lo", set()):
        problems.append(f"C3 loopback {data['loopback']} missing on interface lo")
    if lo is not None and f"network {lo.network} area {area}" not in ospf:
        problems.append(f"C4 loopback network {lo.network} not advertised in area {area}")

    for intf in data["interfaces"]:
        ctx = f"interface {intf['name']}"
        if f"ip address {intf['ip']}" not in cfg.get(ctx, set()):
            problems.append(f"C5 {intf['name']} is missing ip address {intf['ip']}")
        net = _iface(intf["ip"]).network
        if f"network {net} area {area}" not in ospf:
            problems.append(f"C6 {intf['name']} network {net} not advertised in area {area}")

    for ctx in cfg:
        if ctx.startswith("router ") and ctx != "router ospf":
            problems.append(f"C7 unapproved routing protocol: {ctx}")
    return problems

"""Config comparison: intended config vs running config.

No devices needed. Both configs are parsed into {context: {lines}} so that
ordering, `exit` markers and platform noise (frr version, no ipv6 forwarding)
do not cause false drift.
"""
from dataclasses import dataclass, field

# Lines FRR prints (or hides) that are not part of what we manage.
IGNORED_GLOBAL_PREFIXES = (
    "frr version",
    "frr defaults",
    "service integrated-vtysh-config",
    "no ipv6 forwarding",
    "no ip forwarding",
)
IGNORED_CONTEXTS = {"line vty"}
CONTEXT_PREFIXES = ("interface ", "router ", "line ", "vrf ", "route-map ")
SKIP_LINES = ("Building configuration", "Current configuration")


def parse_config(text: str) -> dict:
    """Return {context: set(lines)}. Top-level lines live in the "global" context."""
    contexts = {"global": set()}
    current = "global"
    for raw in text.splitlines():
        stripped = raw.strip()
        if (
            not stripped
            or stripped.startswith("!")
            or stripped == "end"
            or stripped.startswith(SKIP_LINES)
        ):
            continue
        if stripped == "exit":
            current = "global"
            continue
        if not raw[0].isspace():
            if stripped.startswith(CONTEXT_PREFIXES):
                current = stripped
                contexts.setdefault(current, set())
            else:
                current = "global"
                contexts["global"].add(stripped)
        else:
            contexts[current].add(stripped)

    contexts["global"] = {
        line for line in contexts["global"] if not line.startswith(IGNORED_GLOBAL_PREFIXES)
    }
    for ctx in list(contexts):
        if ctx in IGNORED_CONTEXTS:
            del contexts[ctx]
    return contexts


@dataclass
class Drift:
    missing: dict = field(default_factory=dict)  # ctx -> lines expected, not on device
    extra: dict = field(default_factory=dict)  # ctx -> lines on device, not expected
    stale_contexts: list = field(default_factory=list)  # whole blocks to delete

    @property
    def clean(self) -> bool:
        return not (self.missing or self.extra or self.stale_contexts)

    def report(self) -> str:
        if self.clean:
            return "no drift"
        out = ["DRIFT"]
        for ctx in self.stale_contexts:
            out.append(f"  [{ctx}] unexpected block on device")
        for ctx, lines in self.extra.items():
            out += [f"  [{ctx}] unexpected on device: {line}" for line in lines]
        for ctx, lines in self.missing.items():
            out += [f"  [{ctx}] expected but missing: {line}" for line in lines]
        return "\n".join(out)

    def commands(self) -> list:
        """vtysh commands that bring the device back to the intended config.

        Removals go first, then additions, so a changed value is replaced cleanly.
        """

        def order(ctx):
            return (ctx != "global", ctx)

        cmds = ["configure terminal"]
        cmds += [f"no {ctx}" for ctx in self.stale_contexts]
        for ctx in sorted(self.extra, key=order):
            if ctx != "global":
                cmds.append(ctx)
            cmds += [f"no {line}" for line in self.extra[ctx]]
        for ctx in sorted(self.missing, key=order):
            if ctx != "global":
                cmds.append(ctx)
            cmds += list(self.missing[ctx])
        return cmds


def compare(intended_text: str, running_text: str) -> Drift:
    want = parse_config(intended_text)
    have = parse_config(running_text)
    drift = Drift()
    for ctx in sorted(set(want) | set(have)):
        if ctx.startswith("router ") and ctx in have and ctx not in want:
            drift.stale_contexts.append(ctx)
            continue
        wanted = want.get(ctx, set())
        present = have.get(ctx, set())
        if wanted - present:
            drift.missing[ctx] = sorted(wanted - present)
        if present - wanted:
            drift.extra[ctx] = sorted(present - wanted)
    return drift

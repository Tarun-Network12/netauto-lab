# Demo walkthrough

Real output from the lab (three FRR routers, Containerlab, GitHub Codespaces). Nothing here is from an employer.

## 1. Apply from the inventory

```
$ make apply
Inventory OK
--- render_task ---    r1, r2, r3: rendered 21 lines
--- push_task ---      pushed to all three
--- verify_task ---    r1, r2, r3: 2/2 OSPF neighbors Full
```

## 2. Someone changes a router by hand

```
$ make inject-drift
Injected: ip ospf cost 50 on r1 eth2 (not in inventory).

$ make drift
--- drift_task ---
r1  DRIFT
      [interface eth2] unexpected on device: ip ospf cost 50
r2  no drift
r3  no drift
make: *** [drift] Error 1
```

The non-zero exit is on purpose, so a scheduled job or pipeline can alert on it.

## 3. Git keeps the history

```
$ make backup
$ make history
db771f7 backup: running configs 2026-10-15 18:35 UTC
 backups/r1.conf | 1 -
1186ba2 backup: running configs 2026-10-15 18:34 UTC
 backups/r1.conf | 1 +
cc785a2 backup: running configs 2026-10-15 18:34 UTC
 backups/r1.conf | 28 ++++++++++++++++++++++++++++
 backups/r2.conf | 28 ++++++++++++++++++++++++++++
 backups/r3.conf | 28 ++++++++++++++++++++++++++++
```

Commit 1186ba2 is the manual change appearing in the config. db771f7 is the fix.

## 4. Remediate and re-check

```
$ make remediate
r1  DRIFT
      [interface eth2] unexpected on device: ip ospf cost 50
    applied:
      interface eth2
      no ip ospf cost 50
    verified: no drift
r2  no drift, nothing to do
r3  no drift, nothing to do

$ make drift
r1, r2, r3: no drift
```

## 5. Compliance

```
$ make compliance
r1, r2, r3: compliant
```

Rules: hostname, OSPF router-id, loopback, every link advertised in area 0, no unapproved routing protocol.

## 6. Bad inventory stops before it reaches a router

Adding a second `eth2` entry to r1 and running `make validate`:

```
Inventory problems:
  r1: duplicate interface name eth2
  link 10.0.55.0/30: expected exactly 2 routers, found ['r1']
```

## Why the design looks like this

- **Semantic drift compare, not a text diff.** FRR prints header lines, reorders interfaces and adds `exit` markers. Configs are parsed into per-context line sets so only real differences show up.
- **Merge-only push.** Pushing config adds and updates but never removes. That gap is what drift detection and remediation close. It was found for real in this lab when an `ospf_cost` removed from the inventory stayed on the router.
- **Transport.** The routers are containers without SSH, so commands go through `docker exec ... vtysh`. On real gear that one task would use SSH (Netmiko or NAPALM). Render, drift and compliance logic stay the same.

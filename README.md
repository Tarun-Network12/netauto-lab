# netauto-lab

A free network automation lab. Source-of-truth inventory, Jinja2 templates, Nornir push and verify, and tests, all running in containers with no paid tools.

> Status: work in progress. Pieces 1 and 2 of 5 are done.

## Topology

```
        r1 (1.1.1.1)
       /            \
  10.0.12.0/30   10.0.13.0/30
     /                \
r2 (2.2.2.2) -------- r3 (3.3.3.3)
          10.0.23.0/30
```

Three FRRouting routers in a triangle, OSPF area 0.

## How it works

```
inventory/*.yaml  +  templates/frr.conf.j2
        |
        v   (Jinja2 via automation/render.py)
   rendered/r1..r3.conf
        |
        v   (Nornir push task)
   running routers  ->  verify task (OSPF neighbors Full)
```

- `inventory/` is the source of truth: router IDs, loopbacks, interface IPs.
- `templates/frr.conf.j2` generates every router config from that data.
- `tests/` proves the template reproduces the known-good configs byte for byte.
- `automation/netauto.py` renders, pushes and verifies with Nornir.

## Run it (GitHub Codespaces)

1. Click **Code > Codespaces > Create codespace on main**.
2. Wait for setup to finish (about 2 minutes).
3. In the terminal:

```bash
make deploy    # boot the lab
make ospf      # OSPF neighbors on all routers
make test      # template vs golden configs
make apply     # render + push + verify
make destroy   # tear it down
```

## Demo: change traffic with data, not CLI

1. In `inventory/hosts.yaml`, add `ospf_cost: 50` under r1's `eth2` interface.
2. Run `make apply`.
3. Run `make routes`. r1 now reaches 3.3.3.3 through r2 instead of directly.

## Known limits

- The push is merge-only (it adds and updates config, it does not remove). A diff-based push comes with drift detection in piece 3.
- Routers are containers without SSH, so the push uses `docker exec ... vtysh`. On real gear this task would use SSH (Netmiko/NAPALM). Render and verify stay the same.

## Roadmap

- [x] 1. Lab boots with OSPF
- [x] 2. Jinja2 templates and Nornir push
- [ ] 3. Git backups and drift detection
- [ ] 4. Compliance checks and GitHub Actions
- [ ] 5. Docs, diagram and screenshots

## Data note

Lab and synthetic data only. Nothing from any employer.

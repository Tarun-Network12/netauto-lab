# netauto-lab

![CI](https://github.com/Tarun-Network12/netauto-lab/actions/workflows/ci.yml/badge.svg)

A free network automation lab. Source-of-truth inventory, Jinja2 templates, Nornir push and verify, and tests, all running in containers with no paid tools.

> Status: work in progress. Pieces 1 to 4 of 5 are done.

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
- `automation/netauto.py` renders, pushes, verifies, backs up, checks drift and remediates with Nornir.
- `automation/compliance.py` holds the rules: inventory sanity checks and per-config checks (hostname, router-id, loopback, every link advertised in OSPF, no unapproved routing protocol).
- `.github/workflows/ci.yml` runs the tests and `make validate` on every push, no lab needed.
- `automation/drift.py` compares intended vs running config semantically (per-context line sets, platform noise ignored).

## Run it (GitHub Codespaces)

1. Click **Code > Codespaces > Create codespace on main**.
2. Wait for setup to finish (about 2 minutes).
3. In the terminal:

```bash
make deploy    # boot the lab
make ospf      # OSPF neighbors on all routers
make test      # template vs golden configs
make apply     # render + push + verify
make backup    # save running configs and commit to Git
make drift     # running vs intended
make compliance # running configs vs rules
make validate   # inventory + rendered configs, offline (what CI runs)
make destroy   # tear it down
```

## Demo: change traffic with data, not CLI

1. In `inventory/hosts.yaml`, add `ospf_cost: 50` under r1's `eth2` interface.
2. Run `make apply`.
3. Run `make routes`. r1 now reaches 3.3.3.3 through r2 instead of directly.

## Demo: backups and drift detection

```bash
make backup          # first backup, committed to Git
make inject-drift    # someone changes r1 by hand
make drift           # reports the unexpected line, exits 1 on purpose
make backup          # new Git commit with the change
make history         # who/when: see the config change in Git
make remediate       # removes the unexpected line, re-checks
make drift           # no drift
```

Drift is found by comparing the rendered intended config with the device's real `show running-config`, per context, so ordering and FRR header lines do not cause false alarms. Tests use real captured output (`tests/fixtures/`).

## Compliance and CI

`make validate` checks the inventory (duplicate interface names, duplicate IPs, router-id vs loopback, every link has exactly two ends) and then checks every rendered config against the rules. It needs no lab, so GitHub Actions runs it on every push along with the tests. `make compliance` applies the same config rules to the live routers.

Try it: add a duplicate `eth1` entry to r1 in `inventory/hosts.yaml` and run `make validate`. It stops before anything is rendered or pushed.

## Known limits

- `push` is merge-only (adds and updates, never removes). Use `make remediate` to remove unexpected config.
- Routers are containers without SSH, so the push uses `docker exec ... vtysh`. On real gear this task would use SSH (Netmiko/NAPALM). Render and verify stay the same.

## Roadmap

- [x] 1. Lab boots with OSPF
- [x] 2. Jinja2 templates and Nornir push
- [x] 3. Git backups and drift detection
- [x] 4. Compliance checks and GitHub Actions
- [ ] 5. Docs, diagram and screenshots

## Data note

Lab and synthetic data only. Nothing from any employer.

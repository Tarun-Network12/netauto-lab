# netauto-lab

A free, multi-vendor-style network automation lab. Templated configs, Git backups, drift detection and CI compliance checks, all running in containers with no paid tools.

> Status: work in progress. Piece 1 of 5 (lab boots with OSPF) is done.

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

## Run it (GitHub Codespaces)

1. Click **Code > Codespaces > Create codespace on main**.
2. Wait for the setup script to finish (about 2 minutes).
3. In the terminal:

```bash
make deploy    # boot the lab
make ospf      # check OSPF neighbors on all routers
make ping      # r1 pings r3's loopback
make destroy   # tear it down
```

## Roadmap

- [x] 1. Lab boots with OSPF
- [ ] 2. Jinja2 templates and Nornir push
- [ ] 3. Git backups and drift detection
- [ ] 4. Compliance checks and GitHub Actions
- [ ] 5. Docs, diagram and screenshots

## Data note

Lab and synthetic data only. Nothing from any employer.

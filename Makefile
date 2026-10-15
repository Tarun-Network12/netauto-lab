TOPO := topology/netauto.clab.yml
PY   := python3

.PHONY: deploy destroy status ospf routes ping render push verify apply test backup drift remediate history inject-drift validate compliance

deploy:
	sudo containerlab deploy -t $(TOPO)

destroy:
	sudo containerlab destroy -t $(TOPO) --cleanup

status:
	sudo containerlab inspect -t $(TOPO)

ospf:
	@for r in r1 r2 r3; do \
		echo "=== $$r: OSPF neighbors ==="; \
		docker exec clab-netauto-$$r vtysh -c "show ip ospf neighbor" 2>&1 | grep -v "vtysh.conf"; \
	done

routes:
	@docker exec clab-netauto-r1 vtysh -c "show ip route ospf" 2>&1 | grep -v "vtysh.conf"

ping:
	@docker exec clab-netauto-r1 ping -c 3 3.3.3.3

# Automation (piece 2)
render:
	$(PY) automation/netauto.py render

push:
	$(PY) automation/netauto.py push

verify:
	$(PY) automation/netauto.py verify

apply:
	$(PY) automation/netauto.py apply

test:
	$(PY) -m pytest -q

# Backups and drift (piece 3)
backup:
	$(PY) automation/netauto.py backup

drift:
	$(PY) automation/netauto.py drift

remediate:
	$(PY) automation/netauto.py remediate

history:
	git log --oneline --stat -- backups

# Demo helper: change r1 by hand so there is something to detect
inject-drift:
	@docker exec clab-netauto-r1 vtysh -c "configure terminal" -c "interface eth2" -c "ip ospf cost 50" 2>&1 | grep -v "vtysh.conf" || true
	@echo "Injected: ip ospf cost 50 on r1 eth2 (not in inventory). Now run: make drift"

# Compliance and CI (piece 4)
validate:
	$(PY) automation/netauto.py validate

compliance:
	$(PY) automation/netauto.py compliance

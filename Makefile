TOPO := topology/netauto.clab.yml
PY   := python3

.PHONY: deploy destroy status ospf routes ping render push verify apply test

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

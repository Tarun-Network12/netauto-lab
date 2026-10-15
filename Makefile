TOPO := topology/netauto.clab.yml

.PHONY: deploy destroy status ospf routes ping

deploy:
	sudo containerlab deploy -t $(TOPO)

destroy:
	sudo containerlab destroy -t $(TOPO) --cleanup

status:
	sudo containerlab inspect -t $(TOPO)

ospf:
	@for r in r1 r2 r3; do \
		echo "=== $$r: OSPF neighbors ==="; \
		docker exec clab-netauto-$$r vtysh -c "show ip ospf neighbor"; \
	done

routes:
	@docker exec clab-netauto-r1 vtysh -c "show ip route ospf"

ping:
	@docker exec clab-netauto-r1 ping -c 3 3.3.3.3

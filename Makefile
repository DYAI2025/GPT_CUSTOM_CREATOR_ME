.PHONY: install test run sync watch

install:
	pip install -r requirements.txt

test:
	pytest marker_manager/tests -q

run:
	python -m marker_manager.cli gui -c marker_manager/marker_manager_config.yaml

sync:
	python -m marker_manager.cli sync -c marker_manager/marker_manager_config.yaml

watch:
	python -m marker_manager.cli watch -c marker_manager/marker_manager_config.yaml

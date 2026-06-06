test: 
	uv run pytest .

test_watch:
	uv run ptw .

lint:
	uvx ruff check $(filter-out $@,$(MAKECMDGOALS))

typecheck:
	uv run ty check

publish:
	make lint && rm -rf dist && make run_build && make run_upload

run_build:
	uv run --python 3.12 --with build python -m build --wheel


%:
	@:

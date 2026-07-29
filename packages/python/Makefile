test: 
	uv run pytest .

test_watch:
	uv run ptw .

lint:
	uv run ruff check $(filter-out $@,$(MAKECMDGOALS))
	uv run flake8 src

typecheck:
	uv run ty check

publish:
	make lint && rm -rf dist && make run_build && make run_upload

run_build:
	uv run --python 3.10 --with build python -m build --wheel


%:
	@:

.PHONY: install run seed test lint format docker

install:
	pip install -r requirements.txt

run:
	uvicorn app.main:app --reload

seed:
	python -m app.seed

test:
	pytest -v

lint:
	ruff check app tests && ruff format --check app tests

format:
	ruff check --fix app tests && ruff format app tests

docker:
	docker compose up --build

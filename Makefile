.PHONY: install dev test lint run docker-up docker-down

install:
	pip install -r requirements/dev.txt

dev:
	./scripts/run-local.sh

test:
	./scripts/test.sh

lint:
	ruff check app tests

run:
	uvicorn app.main:app --host 0.0.0.0 --port 8001

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down

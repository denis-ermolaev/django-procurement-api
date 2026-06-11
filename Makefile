pre-commit_host:
	uv run pre-commit run --all-files

## Установить pre-commit хуки
pre-commit-install_host:
	uv run pre-commit install

requirements_host:
	uv export --format requirements-txt > requirements.txt

migrate:
	docker compose exec web python manage.py makemigrations api
	docker compose exec web python manage.py migrate


compose_without_build:
	docker compose -f 'docker-compose.yml' up -d --no-build
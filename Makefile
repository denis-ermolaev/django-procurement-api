## Запустить pre-commit хуки
pre-commit_host:
	uv run pre-commit run --all-files

## Запустить тесты на хосте с изолированной SQLite БД
test_host:
	uv run python manage.py test --settings=core.test_settings

## Установить pre-commit хуки
pre-commit-install_host:
	uv run pre-commit install

## (миграции) Создание структуры БД
migrate:
	docker compose exec web python manage.py makemigrations api
	docker compose exec web python manage.py migrate

## Загрузить первоначальные данные в БД
data_to_bd:
	docker compose exec web python manage.py load_shop_data /app/data/shop1.yaml

## Запустить докер без скачивания и проверки
compose_without_build:
	docker compose -f 'docker-compose.yml' up -d --no-build

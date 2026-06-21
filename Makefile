MANAGE := uv run python manage.py
TEST_SETTINGS := core.test_settings
OPENAPI_SCHEMA := /tmp/procurement-openapi.yaml

.PHONY: \
	check_host \
	compose_build \
	compose_without_build \
	coverage_host \
	data_to_bd \
	data_to_bd_shop1 \
	data_to_bd_shop2 \
	makemigrations \
	migrate \
	pre-commit-install_host \
	pre-commit_host \
	schema_validate_host \
	test_host

### Проверки качества
## Запустить тесты, покрытие, OpenAPI validation и pre-commit
check_host: coverage_host schema_validate_host pre-commit_host

## Запустить pre-commit хуки
pre-commit_host:
	uv run pre-commit run --all-files

## Запустить тесты на хосте с изолированной SQLite БД
test_host:
	$(MANAGE) test --settings=$(TEST_SETTINGS)

## Запустить тесты и сформировать отчет покрытия
coverage_host:
	uv run coverage run manage.py test --settings=$(TEST_SETTINGS)
	uv run coverage report
	uv run coverage html

## Проверить OpenAPI schema без предупреждений
schema_validate_host:
	$(MANAGE) spectacular --settings=$(TEST_SETTINGS) --validate --fail-on-warn --file $(OPENAPI_SCHEMA)

## Установить pre-commit хуки
pre-commit-install_host:
	uv run pre-commit install

### База данных
## Создать миграции приложения api
makemigrations:
	docker compose exec web python manage.py makemigrations api

## Применить существующие миграции
migrate:
	docker compose exec web python manage.py migrate

## Загрузить первоначальные данные в БД
data_to_bd:
	$(MAKE) data_to_bd_shop1
	$(MAKE) data_to_bd_shop2

## Загрузить данные первого магазина
data_to_bd_shop1:
	docker compose exec web python manage.py load_shop_data /app/data/shop1.yaml

## Загрузить данные второго магазина
data_to_bd_shop2:
	docker compose exec web python manage.py load_shop_data /app/data/shop2.yaml

### Docker
## Запустить Docker Compose с пересборкой
compose_build:
	docker compose up -d --build

## Запустить Docker Compose без пересборки
compose_without_build:
	docker compose up -d --no-build

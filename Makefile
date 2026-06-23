COMPOSE := docker compose
WEB := $(COMPOSE) exec web
MANAGE := $(WEB) python manage.py
MANAGE_HOST := uv run python manage.py
TEST_SETTINGS := core.test_settings
OPENAPI_SCHEMA := /tmp/procurement-openapi.yaml

.PHONY: \
	check \
	check_host \
	compose_build \
	compose_ps \
	compose_without_build \
	coverage_host \
	data_to_bd \
	data_to_bd_shop1 \
	data_to_bd_shop2 \
	django_check \
	logs_web \
	makemigrations \
	migrate \
	pre-commit-install_host \
	pre-commit \
	pre-commit_host \
	schema_validate \
	schema_validate_host \
	shell \
	showmigrations \
	test \
	test_host

### Проверки качества
## Запустить тесты, OpenAPI validation и pre-commit в контейнерном окружении
check: test schema_validate pre-commit

## Запустить тесты, покрытие, OpenAPI validation и pre-commit
check_host: coverage_host schema_validate_host pre-commit_host

## Запустить pre-commit хуки внутри web-контейнера
pre-commit:
	$(WEB) uv run pre-commit run --all-files

## Запустить pre-commit хуки
pre-commit_host:
	uv run pre-commit run --all-files

## Запустить тесты в web-контейнере на PostgreSQL
test:
	$(MANAGE) test

## Запустить тесты на хосте с изолированной SQLite БД
test_host:
	$(MANAGE_HOST) test --settings=$(TEST_SETTINGS)

## Запустить тесты и сформировать отчет покрытия
coverage_host:
	uv run coverage run manage.py test --settings=$(TEST_SETTINGS)
	uv run coverage report
	uv run coverage html

## Проверить OpenAPI schema без предупреждений в контейнере
schema_validate:
	$(MANAGE) spectacular --validate --fail-on-warn --file $(OPENAPI_SCHEMA)

## Проверить OpenAPI schema без предупреждений
schema_validate_host:
	$(MANAGE_HOST) spectacular --settings=$(TEST_SETTINGS) --validate --fail-on-warn --file $(OPENAPI_SCHEMA)

## Установить pre-commit хуки
pre-commit-install_host:
	uv run pre-commit install

## Запустить Django system check в контейнере
django_check:
	$(MANAGE) check

### База данных
## Создать миграции приложения api
makemigrations:
	$(MANAGE) makemigrations api

## Применить существующие миграции
migrate:
	$(MANAGE) migrate

## Показать состояние миграций приложения api
showmigrations:
	$(MANAGE) showmigrations api

## Загрузить первоначальные данные в БД
data_to_bd:
	$(MAKE) data_to_bd_shop1
	$(MAKE) data_to_bd_shop2

## Загрузить данные первого магазина
data_to_bd_shop1:
	$(MANAGE) load_shop_data /app/data/shop1.yaml

## Загрузить данные второго магазина
data_to_bd_shop2:
	$(MANAGE) load_shop_data /app/data/shop2.yaml

### Docker
## Запустить Docker Compose с пересборкой
compose_build:
	$(COMPOSE) up -d --build

## Запустить Docker Compose без пересборки
compose_without_build:
	$(COMPOSE) up -d --no-build

## Показать состояние контейнеров
compose_ps:
	$(COMPOSE) ps

## Смотреть логи web-контейнера
logs_web:
	$(COMPOSE) logs -f web

## Открыть shell в web-контейнере
shell:
	$(WEB) bash

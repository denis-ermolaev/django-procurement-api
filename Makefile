COMPOSE := docker compose
WEB := $(COMPOSE) exec web
MANAGE := $(WEB) python manage.py
MANAGE_HOST := uv run python manage.py
TEST_SETTINGS := core.test_settings
OPENAPI_SCHEMA := tmp/procurement-openapi.yaml

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
	data_to_bd_shop3 \
	data_to_bd_shop4 \
	django_check \
	init \
	logs_web \
	makemigrations \
	migrate \
	pre-commit-install_host \
	pre-commit \
	pre-commit_host \
	pre-commit_changed_host \
	schema_validate \
	schema_validate_host \
	shell \
	showmigrations \
	test \
	test_host \
	test_up \
	test_down

### Проверки качества
## Запустить тесты, OpenAPI validation и pre-commit в контейнерном окружении
check: test schema_validate pre-commit

## Запустить тесты, покрытие, OpenAPI validation и pre-commit на хосте
check_host: coverage_host schema_validate_host pre-commit_host

## Запустить pre-commit хуки внутри web-контейнера
pre-commit:
	$(WEB) uv run pre-commit run --all-files

## Запустить pre-commit хуки на хосте (на всех файлах — полная проверка)
pre-commit_host:
	uv run pre-commit run --all-files

## Прогнать mypy, ty, ruff format и ruff check на всех файлах
check_code:
	uv run mypy .
	uv run ty check
	uv run ruff format
	uv run ruff check --fix

## Поднять одноразовый test-db и ждать готовности (healthcheck)
test_up:
	$(COMPOSE) --profile test up -d test-db --wait --no-build

## Остановить и удалить одноразовый test-db (без volume)
test_down:
	$(COMPOSE) stop test-db 2>/dev/null || true
	$(COMPOSE) rm -f -v test-db 2>/dev/null || true

## Запустить тесты на одноразовом PostgreSQL test-db
test: test_up
	$(MANAGE) test --settings=$(TEST_SETTINGS) || ( $(MAKE) test_down && exit 1 )
	$(MAKE) test_down

## Запустить тесты на хосте с тестовой PostgreSQL БД
test_host:
	$(MANAGE_HOST) test --settings=$(TEST_SETTINGS) 2>/dev/null || echo "⚠ test_host — используйте make test (контейнер)"

## Запустить тесты и сформировать отчет покрытия (артефакты в tmp/)
coverage_host:
	COVERAGE_FILE=tmp/.coverage uv run coverage run manage.py test --settings=$(TEST_SETTINGS)
	COVERAGE_FILE=tmp/.coverage uv run coverage report
	COVERAGE_FILE=tmp/.coverage uv run coverage html -d tmp/htmlcov

## Проверить OpenAPI schema без предупреждений в контейнере
schema_validate:
	$(MANAGE) spectacular --validate --fail-on-warn --file $(OPENAPI_SCHEMA)

## Проверить OpenAPI schema без предупреждений на хосте
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

## Инициализация БД: миграции + первоначальные данные
init:
	$(MAKE) migrate
	$(MAKE) data_to_bd

## Применить существующие миграции
migrate:
	$(MANAGE) migrate --noinput

## Показать состояние миграций приложения api
showmigrations:
	$(MANAGE) showmigrations api

## Загрузить первоначальные данные всех магазинов в БД
data_to_bd:
	$(MAKE) data_to_bd_shop1
	$(MAKE) data_to_bd_shop2
	$(MAKE) data_to_bd_shop3
	$(MAKE) data_to_bd_shop4

## Загрузить данные первого магазина
data_to_bd_shop1:
	$(MANAGE) load_shop_data /app/data/shop1.yaml

## Загрузить данные второго магазина
data_to_bd_shop2:
	$(MANAGE) load_shop_data /app/data/shop2.yaml

## Загрузить данные третьего магазина
data_to_bd_shop3:
	$(MANAGE) load_shop_data /app/data/shop3.yaml

## Загрузить данные четвёртого магазина
data_to_bd_shop4:
	$(MANAGE) load_shop_data /app/data/shop4.yaml

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

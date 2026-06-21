# 1. Проверки качества ----
## 1.1. Запустить pre-commit хуки ----
pre-commit_host:
	uv run pre-commit run --all-files

## 1.2. Запустить тесты на хосте с изолированной SQLite БД ----
test_host:
	uv run python manage.py test --settings=core.test_settings

## 1.3. Установить pre-commit хуки ----
pre-commit-install_host:
	uv run pre-commit install

# 2. База данных ----
## 2.1. Создание и применение миграций ----
migrate:
	docker compose exec web python manage.py makemigrations api
	docker compose exec web python manage.py migrate

## 2.2. Загрузить первоначальные данные в БД ----
data_to_bd:
	$(MAKE) data_to_bd_shop1
	$(MAKE) data_to_bd_shop2

## 2.3. Загрузить данные первого магазина ----
data_to_bd_shop1:
	docker compose exec web python manage.py load_shop_data /app/data/shop1.yaml

## 2.4. Загрузить данные второго магазина ----
data_to_bd_shop2:
	docker compose exec web python manage.py load_shop_data /app/data/shop2.yaml

# 3. Docker ----
## 3.1. Запустить Docker Compose без пересборки ----
compose_without_build:
	docker compose -f 'docker-compose.yml' up -d --no-build

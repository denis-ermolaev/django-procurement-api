## Подготовка окружения
Сделать копию файла ".env.example" с именем ".env"

```bash
# Подготовка контейнеров
docker compose -f 'docker-compose.yml' up -d --build

# Миграции БД
make migrate

# Загрузка предварительных данных в БД
make data_to_bd

```

## Регистрация
`http://localhost:8000/api/docs/` - интерактивная документация

1) POST - `/api/auth/users/` - регестрация нового пользователя
2) В консоль придёт письмо e-mail письмо `docker logs --tail 1000 -f web`
3) POST - `/api/auth/users/activation/` вставить uid и token для подтверждения аккаунта
4) Получение токена - POST `/api/auth/jwt/create/` и access токен используем для запросов


Или с помощью `docker compose exec web python manage.py createsuperuser` - создание супер пользователя

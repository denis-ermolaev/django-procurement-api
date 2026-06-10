pre-commit_host:
	uv run pre-commit run --all-files

## Установить pre-commit хуки
pre-commit-install_host:
	uv run pre-commit install

requirements_host:
	uv export --format requirements-txt > requirements.txt

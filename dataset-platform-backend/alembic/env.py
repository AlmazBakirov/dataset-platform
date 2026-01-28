import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from app.core.config import settings

# Alembic Config
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 1) DATABASE_URL должен быть задан в окружении
database_url = os.getenv("DATABASE_URL") or settings.database_url
if not database_url:
    raise RuntimeError("DATABASE_URL is not set and settings.database_url is empty")

# Передаём URL в Alembic
config.set_main_option("sqlalchemy.url", database_url)

# 2) Подключаем Base.metadata
# ВАЖНО: чаще всего Base лежит в app/db/session.py
# Если у вас иначе — поправьте импорт ниже.
from app.db.session import Base  # noqa: E402

# 3) Обязательно импортируем модели, чтобы autogenerate видел таблицы
# Если какие-то файлы называются иначе — замените имена.
try:
    import app.models.user  # noqa: F401
    import app.models.request  # noqa: F401
    import app.models.image  # noqa: F401
    import app.models.task  # noqa: F401
    import app.models.annotation  # noqa: F401
    import app.models.qc  # noqa: F401
except Exception:
    # Даже если autogenerate не нужен — миграции всё равно будут работать.
    pass

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Offline migrations."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Online migrations."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section) or {},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

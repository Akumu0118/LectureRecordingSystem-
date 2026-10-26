from alembic import context
from sqlalchemy import text

from app.core.database import Base, get_engine
from app.core.config import get_settings
from app import models  # noqa: F401 -- registers models with Base.metadata

target_metadata = Base.metadata


def include_name(name, type_, parent_names):
    # Autogeneration must not propose dropping unrelated existing tables.
    return type_ != "table" or name in target_metadata.tables


def configure_online(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        include_name=include_name,
        version_table_schema=connection.execute(text("SELECT current_schema()")).scalar_one(),
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    database_url = get_settings().database_url
    if database_url is None:
        raise RuntimeError("Configure DATABASE_URL in backend/.env before running Alembic")
    context.configure(
        url=database_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        configure_online(connection)
        return
    engine = get_engine()
    try:
        with engine.connect() as connection:
            configure_online(connection)
            connection.commit()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

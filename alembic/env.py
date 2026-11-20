from alembic import context

from app.core.config import Settings
from app.db.models import Base
from app.db.session import build_engine

settings = Settings()
url = context.config.attributes.get("database_url") or settings.database_url
if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = build_engine(url, busy_timeout_ms=settings.sqlite_busy_timeout_ms)
    try:
        with engine.begin() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()

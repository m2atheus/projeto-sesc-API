"""Indexar consultas por data sem alterar linhas existentes."""
from alembic import op

revision = "0002_time_index"
down_revision = "0001_weather"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_observations_measured", "observations", ["measured_at_utc"])


def downgrade() -> None:
    op.drop_index("ix_observations_measured", table_name="observations")

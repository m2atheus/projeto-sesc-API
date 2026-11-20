"""Estações e observações meteorológicas."""
from alembic import op
import sqlalchemy as sa

revision = "0001_weather"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("mac_address", sa.String(17), nullable=False, unique=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("model", sa.String(50), nullable=False),
        sa.Column("is_simulated", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "observations",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("station_id", sa.Integer, sa.ForeignKey("stations.id"), nullable=False),
        sa.Column("measured_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outdoor_temperature_c", sa.Float),
        sa.Column("indoor_temperature_c", sa.Float),
        sa.Column("outdoor_humidity_pct", sa.Float),
        sa.Column("indoor_humidity_pct", sa.Float),
        sa.Column("wind_speed_ms", sa.Float),
        sa.Column("wind_gust_ms", sa.Float),
        sa.Column("wind_direction_deg", sa.Float),
        sa.Column("wind_gust_direction_deg", sa.Float),
        sa.Column("daily_rain_mm", sa.Float),
        sa.Column("hourly_rain_mm", sa.Float),
        sa.Column("weekly_rain_mm", sa.Float),
        sa.Column("monthly_rain_mm", sa.Float),
        sa.Column("yearly_rain_mm", sa.Float),
        sa.Column("absolute_pressure_hpa", sa.Float),
        sa.Column("relative_pressure_hpa", sa.Float),
        sa.Column("uv_index", sa.Float),
        sa.Column("solar_radiation_wm2", sa.Float),
        sa.Column("raw_payload", sa.JSON, nullable=False),
        sa.UniqueConstraint("station_id", "measured_at_utc", name="uq_observation_station_time"),
    )
    op.create_index("ix_observations_received", "observations", ["station_id", "received_at_utc", "id"])


def downgrade() -> None:
    op.drop_table("observations")
    op.drop_table("stations")

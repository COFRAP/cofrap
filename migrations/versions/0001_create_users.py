"""Crée les utilisateurs et les capacités temporaires de remise / authentification."""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True)),
        sa.Column("expired", sa.Boolean(), nullable=False),
        sa.Column("mfa_confirmed", sa.Boolean(), nullable=False),
        sa.Column("totp_ciphertext", sa.Text()),
        sa.Column("last_totp_step", sa.BigInteger()),
        sa.Column("delivery_ciphertext", sa.Text()),
        *[
            column
            for purpose in ("delivery", "enrollment", "renewal", "session")
            for column in (
                sa.Column(f"{purpose}_digest", sa.String(64), unique=True),
                sa.Column(f"{purpose}_expires_at", sa.DateTime(timezone=True)),
            )
        ],
    )


def downgrade():
    op.drop_table("users")

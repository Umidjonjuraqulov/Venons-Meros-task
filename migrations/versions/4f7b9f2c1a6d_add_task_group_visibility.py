"""add task group visibility

Revision ID: 4f7b9f2c1a6d
Revises: 35369e449604
Create Date: 2026-09-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4f7b9f2c1a6d"
down_revision: Union[str, None] = "3361b04ae8de"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "task_groups",
        sa.Column("visible", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.execute(sa.text("UPDATE task_groups SET visible = TRUE"))


def downgrade() -> None:
    op.drop_column("task_groups", "visible")
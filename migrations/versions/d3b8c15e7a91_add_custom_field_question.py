"""add custom field question text

Revision ID: d3b8c15e7a91
Revises: c7a1e9f3b204
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3b8c15e7a91"
down_revision: Union[str, None] = "c7a1e9f3b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("custom_fields", sa.Column("question", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("custom_fields", "question")

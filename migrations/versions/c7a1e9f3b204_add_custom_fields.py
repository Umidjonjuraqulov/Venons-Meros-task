"""add custom fields for task groups

Revision ID: c7a1e9f3b204
Revises: 4f7b9f2c1a6d
Create Date: 2026-09-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7a1e9f3b204"
down_revision: Union[str, None] = "4f7b9f2c1a6d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "custom_fields",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("field_type", sa.String(), nullable=False),
        sa.Column("ask_stage", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["task_groups.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_fields_group_id", "custom_fields", ["group_id"])

    op.create_table(
        "custom_field_options",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["custom_fields.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_field_options_field_id", "custom_field_options", ["field_id"])

    op.create_table(
        "task_custom_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=True),
        sa.Column("field_title", sa.String(), nullable=False),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("sort", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_id"], ["custom_fields.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_task_custom_values_task_id", "task_custom_values", ["task_id"])


def downgrade() -> None:
    op.drop_index("ix_task_custom_values_task_id", table_name="task_custom_values")
    op.drop_table("task_custom_values")
    op.drop_index("ix_custom_field_options_field_id", table_name="custom_field_options")
    op.drop_table("custom_field_options")
    op.drop_index("ix_custom_fields_group_id", table_name="custom_fields")
    op.drop_table("custom_fields")

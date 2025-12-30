from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'dbe94bc4415b'
down_revision = 'b7691686dcee'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('task_groups', 'ban_minutes', new_column_name='ban_hours')


def downgrade() -> None:
    op.alter_column('task_groups', 'ban_hours', new_column_name='ban_minutes')

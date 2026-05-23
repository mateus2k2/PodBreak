"""add post_id to task

Revision ID: a1b2c3d4e5f6
Revises: 0e37bd110dc0
Create Date: 2026-03-22 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '0e37bd110dc0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.add_column(sa.Column('post_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_task_post_id', 'post', ['post_id'], ['id'])


def downgrade():
    with op.batch_alter_table('task', schema=None) as batch_op:
        batch_op.drop_constraint('fk_task_post_id', type_='foreignkey')
        batch_op.drop_column('post_id')

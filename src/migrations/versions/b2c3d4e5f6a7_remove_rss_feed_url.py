"""remove rss_feed_url from post and callback_url from model_call

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-24 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.drop_column('rss_feed_url')

    with op.batch_alter_table('model_call', schema=None) as batch_op:
        batch_op.drop_column('callback_url')


def downgrade():
    with op.batch_alter_table('post', schema=None) as batch_op:
        batch_op.add_column(sa.Column('rss_feed_url', sa.Text(), nullable=True))

    with op.batch_alter_table('model_call', schema=None) as batch_op:
        batch_op.add_column(sa.Column('callback_url', sa.Text(), nullable=True))

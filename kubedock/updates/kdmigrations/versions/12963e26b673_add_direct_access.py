"""add direct access

Revision ID: 12963e26b673
Revises: 1a24688cc541
Create Date: 2016-07-01 06:33:38.183747

"""

# revision identifiers, used by Alembic.
revision = '12963e26b673'
down_revision = '1a24688cc541'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('pods', sa.Column('direct_access', sa.TEXT(), autoincrement=False, nullable=True))


def downgrade():
    op.drop_column('pods', 'direct_access')

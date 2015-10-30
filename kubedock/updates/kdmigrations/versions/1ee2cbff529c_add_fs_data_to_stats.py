"""add fs_data to stats

Revision ID: 1ee2cbff529c
Revises: 3505518f6f4f
Create Date: 2015-10-30 20:23:23.182514

"""

# revision identifiers, used by Alembic.
revision = '1ee2cbff529c'
down_revision = '3505518f6f4f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('stat_wrap_5min', sa.Column('fs_data', sa.String(255), nullable=True))


def downgrade():
    op.drop_column('stat_wrap_5min', 'fs_data')

"""empty message

Revision ID: 46bba639e6fb
Revises: 27ac98113841
Create Date: 2016-02-05 07:06:29.186960

"""

# revision identifiers, used by Alembic.
revision = '46bba639e6fb'
down_revision = '27ac98113841'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('system_settings', sa.Column('options', sa.String(), nullable=True))


def downgrade():
    op.drop_column('system_settings', 'options')

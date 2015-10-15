"""Add hash to PredefinedApp model

Revision ID: 299957c24510
Revises: 33b1e3a97fb8
Create Date: 2015-10-13 18:26:06.849909

"""

# revision identifiers, used by Alembic.
revision = '299957c24510'
down_revision = '33b1e3a97fb8'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('predefined_apps', sa.Column('qualifier', sa.String(40),
                  server_default='', nullable=False, index=True))


def downgrade():
    op.drop_column('predefined_apps', 'qualifier')

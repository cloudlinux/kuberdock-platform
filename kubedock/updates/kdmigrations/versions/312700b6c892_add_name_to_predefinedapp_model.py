"""Add name to PredefinedApp model

Revision ID: 299957c24510
Revises: 18f6b46d5b6c
Create Date: 2015-10-13 18:26:06.849909

"""

# revision identifiers, used by Alembic.
revision = '312700b6c892'
down_revision = '299957c24510'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('predefined_apps', sa.Column('name', sa.String(255),
                  server_default='', nullable=False))


def downgrade():
    op.drop_column('predefined_apps', 'name')

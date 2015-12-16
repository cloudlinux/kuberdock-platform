"""add_origin_col_to_predefined_apps

Revision ID: 32e6666ff6d0
Revises: 46b5b819ba35
Create Date: 2015-12-10 16:48:47.775404

"""

# revision identifiers, used by Alembic.
revision = '32e6666ff6d0'
down_revision = '46b5b819ba35'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('predefined_apps', sa.Column('origin', sa.String(255),
                  nullable=False, server_default='unknown'))

def downgrade():
    op.drop_column('predefined_apps', 'origin')

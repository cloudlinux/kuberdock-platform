"""Add User.deleted column

Revision ID: 33ae2dd8e49b
Revises: 28b23145af40
Create Date: 2015-11-04 19:39:11.270502

"""

# revision identifiers, used by Alembic.
revision = '33ae2dd8e49b'
down_revision = '28b23145af40'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('deleted', sa.Boolean(),
                  nullable=False, server_default='False'))


def downgrade():
    op.drop_column('users', 'deleted')

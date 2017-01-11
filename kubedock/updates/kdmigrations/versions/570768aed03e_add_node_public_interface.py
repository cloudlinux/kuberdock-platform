"""Add Node.public_interface

Revision ID: 570768aed03e
Revises: 1f26cf5abc0f
Create Date: 2017-01-11 22:48:43.737880

"""

# revision identifiers, used by Alembic.
revision = '570768aed03e'
down_revision = '1f26cf5abc0f'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('nodes', sa.Column('public_interface', sa.String(15),
                                     nullable=True))


def downgrade():
    op.drop_column('nodes', 'public_interface')

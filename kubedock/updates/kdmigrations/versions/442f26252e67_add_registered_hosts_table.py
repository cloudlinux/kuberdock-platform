"""add registered_hosts table

Revision ID: 442f26252e67
Revises: 4912523d89cb
Create Date: 2015-12-29 13:19:01.340214

"""

# revision identifiers, used by Alembic.
revision = '442f26252e67'
down_revision = '4912523d89cb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('registered_hosts',
        sa.Column(sa.Integer, primary_key=True, nullable=False, autoincrement=True),
        sa.Column(sa.String, nullable=False, unique=True),
        sa.Column(sa.Text, nullable=True),
        sa.Column(sa.DateTime, nullable=False))


def downgrade():
        op.drop_table('registered_hosts')

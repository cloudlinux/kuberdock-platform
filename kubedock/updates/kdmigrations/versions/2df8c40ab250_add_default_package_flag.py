"""Add is_default flag to packages

Revision ID: 2df8c40ab250
Revises: 46bba639e6fb
Create Date: 2016-02-09 22:21:55.489017

"""

# revision identifiers, used by Alembic.
revision = '2df8c40ab250'
down_revision = '46bba639e6fb'

from alembic import op
import sqlalchemy as sa


def upgrade():
    bind = op.get_bind()
    op.add_column('packages', sa.Column('is_default', sa.Boolean(), nullable=True))
    op.create_unique_constraint(None, 'packages', ['is_default'])
    bind.execute("UPDATE packages SET is_default=true WHERE id in (SELECT MIN(id) FROM packages)")


def downgrade():
    op.drop_constraint('packages_is_default_key', 'packages', type_='unique')
    op.drop_column('packages', 'is_default')

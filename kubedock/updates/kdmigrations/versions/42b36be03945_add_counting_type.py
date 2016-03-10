"""add counting type

Revision ID: 42b36be03945
Revises: 27c8f4c5f242
Create Date: 2016-03-10 10:28:03.769798

"""

# revision identifiers, used by Alembic.
revision = '42b36be03945'
down_revision = '27c8f4c5f242'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('packages', sa.Column('count_type', sa.String, nullable=True))


def downgrade():
    op.drop_column('packages', 'count_type')

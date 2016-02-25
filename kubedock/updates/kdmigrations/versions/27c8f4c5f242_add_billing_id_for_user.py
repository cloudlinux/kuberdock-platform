"""add billing id for user

Revision ID: 27c8f4c5f242
Revises: 4ded025d2f29
Create Date: 2016-02-24 15:21:29.792495

"""

# revision identifiers, used by Alembic.
revision = '27c8f4c5f242'
down_revision = '4ded025d2f29'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('users', sa.Column('clientid', sa.Integer, nullable=True, unique=True))


def downgrade():
    op.drop_column('users', 'clientid')

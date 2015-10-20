"""PersistentDiskState.user_id nullable

Revision ID: 3a8320be841c
Revises: 1139a080f512
Create Date: 2015-10-20 07:17:08.792600

"""

# revision identifiers, used by Alembic.
revision = '3a8320be841c'
down_revision = '1139a080f512'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('pd_states', 'user_id',
                    existing_type=sa.INTEGER(), nullable=True)


def downgrade():
    op.alter_column('pd_states', 'user_id',
                    existing_type=sa.INTEGER(), nullable=False)

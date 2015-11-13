"""empty message

Revision ID: 3d2db4a87f86
Revises: 5049471549ba
Create Date: 2015-11-10 21:58:22.428392

"""

# revision identifiers, used by Alembic.
revision = '3d2db4a87f86'
down_revision = '5049471549ba'

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('rbac_role', sa.Column('internal', sa.Boolean(),
                                         nullable=False,
                                         server_default='False'))


def downgrade():
    op.drop_column('rbac_role', 'internal')

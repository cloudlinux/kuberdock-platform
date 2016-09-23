"""Added impersonated_id to session_data

Revision ID: 11bf9b6a89b2
Revises: 3149fa6dc22b
Create Date: 2016-09-23 12:11:24.373622

"""

# revision identifiers, used by Alembic.
revision = '11bf9b6a89b2'
down_revision = '50451812ee04'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.add_column('session_data',
                  sa.Column('impersonated_id', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('session_data', 'impersonated_id')

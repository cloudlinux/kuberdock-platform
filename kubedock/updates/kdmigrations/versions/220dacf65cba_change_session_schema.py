"""change session schema

Revision ID: 220dacf65cba
Revises: 45e4b1e232ad
Create Date: 2016-05-09 14:23:42.761748

"""

# revision identifiers, used by Alembic.
revision = '220dacf65cba'
down_revision = '45e4b1e232ad'

from alembic import op
import sqlalchemy as sa


def upgrade():
    conn = op.get_bind()
    conn.execute("DELETE FROM session_data")
    op.drop_column('session_data', 'data')
    op.add_column('session_data', sa.Column(
        'role_id', sa.Integer(), nullable=False))


def downgrade():
    op.drop_column('session_data', 'role_id')
    op.add_column('session_data', sa.Column('data', sa.PickleType, nullable=True))

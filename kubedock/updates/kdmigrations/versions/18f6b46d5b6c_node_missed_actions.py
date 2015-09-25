"""node missed actions

Revision ID: 18f6b46d5b6c
Revises: 30bf03408b5e
Create Date: 2015-09-25 16:18:31.492789

"""

# revision identifiers, used by Alembic.
revision = '18f6b46d5b6c'
down_revision = '30bf03408b5e'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.create_table('node_missed_actions',
                    sa.Column('host', sa.String(255), primary_key=True, nullable=False),
                    sa.Column('command', sa.Text, nullable=False),
                    sa.Column('time_stamp', sa.DateTime, primary_key=True, nullable=False))


def downgrade():
    op.drop_table('node_missed_actions')

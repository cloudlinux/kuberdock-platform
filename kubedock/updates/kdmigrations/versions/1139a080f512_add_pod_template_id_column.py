"""add_pod_template_id_column

Revision ID: 1139a080f512
Revises: 312700b6c892
Create Date: 2015-09-25 15:39:43.426778

"""

# revision identifiers, used by Alembic.
revision = '1139a080f512'
down_revision = '312700b6c892'

from alembic import op
import sqlalchemy as sa


def upgrade():
    # THIS COMMAND MOVED TO 00020_update.py
    # op.add_column('pods', sa.Column('template_id', sa.Integer(), nullable=True))
    pass


def downgrade():
    # THIS COMMAND MOVED TO 00020_update.py
    # op.drop_column('pods', 'template_id')
    pass

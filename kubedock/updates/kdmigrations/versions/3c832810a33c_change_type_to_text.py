"""change type to text

Revision ID: 3c832810a33c
Revises: 45e4b1e232ad
Create Date: 2016-05-16 09:55:57.788558

"""

# revision identifiers, used by Alembic.
revision = '3c832810a33c'
down_revision = '220dacf65cba'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.alter_column('notification_roles', 'target', type_=sa.Text)
    op.alter_column('notifications', 'message', type_=sa.Text)


def downgrade():
    op.alter_column('notification_roles', 'target', type_=sa.String(255))
    op.alter_column('notifications', 'message', type_=sa.String(255))

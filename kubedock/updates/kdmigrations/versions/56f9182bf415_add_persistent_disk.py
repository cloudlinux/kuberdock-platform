"""Add PersistetnDisk

Revision ID: 56f9182bf415
Revises: 1ee2cbff529c
Create Date: 2015-11-02 01:34:40.942580

"""

# revision identifiers, used by Alembic.
revision = '56f9182bf415'
down_revision = '1ee2cbff529c'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


def upgrade():
    op.create_table(
        'persistent_disk',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('drive_name', sa.String(length=64), nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('size', sa.Integer(), nullable=False),
        sa.Column('pod_id', postgresql.UUID(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['pod_id'], ['pods.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('drive_name'),
        sa.UniqueConstraint('name', 'owner_id')
    )


def downgrade():
    op.drop_table('persistent_disk')

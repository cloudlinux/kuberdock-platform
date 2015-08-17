"""Disk space limits in MB

Revision ID: 144bf08f16b
Revises: None
Create Date: 2015-08-17 11:15:40.550755

"""

revision = '144bf08f16b'
down_revision = None

from alembic import op
import sqlalchemy as sa


from kubedock.billing.models import Kube


def upgrade():
    op.add_column('kubes', sa.Column('disk_space_units', sa.String(3),
                  server_default='MB', nullable=False))

    session = sa.orm.sessionmaker()(bind=op.get_bind())

    for kube in session.query(Kube).all():
        kube.disk_space /= 2 ** 20

    session.commit()


def downgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())

    for kube in session.query(Kube).all():
        kube.disk_space *= 2 ** 20

    session.commit()

    op.drop_column('kubes', 'disk_space_units')

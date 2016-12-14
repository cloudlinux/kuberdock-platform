"""Add kube_id field to PodState

Revision ID: 50e4a32fa6c3
Revises: 81398dd39d6
Create Date: 2016-10-14 15:48:59.602985

"""

# revision identifiers, used by Alembic.
revision = '50e4a32fa6c3'
down_revision = '81398dd39d6'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects import postgresql

Base = declarative_base()


class Pod(Base):
    __tablename__ = 'pods'
    id = sa.Column(postgresql.UUID, primary_key=True, nullable=False)
    kube_id = sa.Column(sa.Integer)


class PodState(Base):
    __tablename__ = 'pod_states'

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    pod_id = sa.Column(postgresql.UUID, nullable=False)
    kube_id = sa.Column(sa.Integer, nullable=False)


def upgrade():
    op.add_column('pod_states', sa.Column('kube_id', sa.Integer(),
                                          nullable=True))

    session = sa.orm.sessionmaker()(bind=op.get_bind())
    for (pod_id, kube_id) in session.query(Pod.id, Pod.kube_id):
        session.query(PodState).filter_by(pod_id=pod_id).update(
            {'kube_id': kube_id})
    session.commit()

    op.alter_column('pod_states', 'kube_id', nullable=False)


def downgrade():
    op.drop_column('pod_states', 'kube_id')

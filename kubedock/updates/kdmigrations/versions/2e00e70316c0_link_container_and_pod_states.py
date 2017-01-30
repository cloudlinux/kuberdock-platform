
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

"""Link ContainerStates and PodStates

Revision ID: 2e00e70316c0
Revises: 3d2db4a87f86
Create Date: 2015-11-12 02:10:26.471169

"""

# revision identifiers, used by Alembic.
revision = '2e00e70316c0'
down_revision = '3d2db4a87f86'

from collections import defaultdict
from datetime import timedelta, datetime
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Session = sessionmaker()
Base = declarative_base()


class Pod(Base):
    __tablename__ = 'pods'
    id = sa.Column(postgresql.UUID, primary_key=True, nullable=False)


class ContainerState(Base):
    __tablename__ = 'container_states'
    pod_id = sa.Column(sa.ForeignKey('pods.id'), nullable=False)
    pod_state_id = sa.Column(sa.ForeignKey('pod_states.id'), nullable=False)
    docker_id = sa.Column(sa.String(length=80), primary_key=True, nullable=False)
    container_name = sa.Column(sa.String(length=255), primary_key=True, nullable=False)
    start_time = sa.Column(sa.DateTime, primary_key=True, nullable=False)
    end_time = sa.Column(sa.DateTime, nullable=True)


class PodState(Base):
    __tablename__ = 'pod_states'
    __table_args__ = (sa.Index('ix_pod_id_start_time',
                               'pod_id', 'start_time', unique=True),)

    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    pod_id = sa.Column(postgresql.UUID, sa.ForeignKey('pods.id'), nullable=False)
    start_time = sa.Column(sa.DateTime, nullable=False)
    end_time = sa.Column(sa.DateTime, nullable=True)


def upgrade_data():
    session = Session(bind=op.get_bind())

    unknown_pod_states = defaultdict(list)

    for cs in session.query(ContainerState).all():
        pod_state = session.query(PodState).filter(
            PodState.pod_id == cs.pod_id,
            PodState.start_time <= cs.start_time,
        ).order_by(PodState.start_time.desc()).first()
        if pod_state is None:
            unknown_pod_states[cs.pod_id].append(cs)
        else:
            cs.pod_state_id = pod_state.id

    for pod_id, container_states in unknown_pod_states.iteritems():
        start, end = None, datetime(1970, 1, 1)
        for cs in container_states:
            if start is None or cs.start_time < start:
                start = cs.start_time
            if end is not None and (cs.end_time is None or cs.end_time > end):
                end = cs.end_time
        start -= timedelta(seconds=3)
        if end is not None:
            end += timedelta(seconds=3)
        pod_state = PodState(pod_id=pod_id, start_time=start, end_time=end)
        session.add(pod_state)
        session.flush()
        for cs in container_states:
            cs.pod_state_id = pod_state.id

    session.commit()


def downgrade_data():
    session = Session(bind=op.get_bind())

    for cs in session.query(ContainerState).all():
        cs.pod_id = session.query(PodState).get(cs.pod_state_id).pod_id
    session.commit()


def upgrade():
    op.execute(sa.schema.CreateSequence(sa.Sequence('pod_states_id_seq')))
    op.add_column('pod_states', sa.Column('id', sa.Integer(), nullable=False,
                  server_default=sa.text("nextval('pod_states_id_seq'::regclass)")))
    op.execute("ALTER TABLE pod_states DROP CONSTRAINT pod_states_pkey, "
               "ADD CONSTRAINT pod_states_pkey PRIMARY KEY (id);")

    op.add_column('container_states', sa.Column('exit_code', sa.Integer(), nullable=True))
    op.add_column('container_states', sa.Column('pod_state_id', sa.Integer(), nullable=True))
    op.add_column('container_states', sa.Column('reason', sa.Text(), nullable=True))
    op.create_index('ix_pod_id_start_time', 'pod_states', ['pod_id', 'start_time'], unique=True)
    op.create_foreign_key('container_states_pod_state_id_fkey', 'container_states',
                          'pod_states', ['pod_state_id'], ['id'])

    upgrade_data()

    op.alter_column('container_states', 'pod_state_id',
                    existing_type=sa.INTEGER(), nullable=False)
    op.drop_constraint(u'container_states_pod_id_fkey', 'container_states',
                       type_='foreignkey')
    op.drop_column('container_states', 'pod_id')


def downgrade():
    op.add_column('container_states', sa.Column('pod_id', postgresql.UUID(),
                  autoincrement=False, nullable=True))
    op.create_foreign_key(u'container_states_pod_id_fkey',
                          'container_states', 'pods', ['pod_id'], ['id'])

    downgrade_data()

    op.drop_column('container_states', 'reason')
    op.drop_column('container_states', 'exit_code')
    op.drop_constraint('container_states_pod_state_id_fkey', 'container_states',
                       type_='foreignkey')
    op.drop_index('ix_pod_id_start_time', table_name='pod_states')
    op.drop_column('container_states', 'pod_state_id')
    op.execute("ALTER TABLE pod_states DROP CONSTRAINT pod_states_pkey, "
               "ADD CONSTRAINT pod_states_pkey PRIMARY KEY (pod_id, start_time);")
    op.drop_column('pod_states', 'id')
    op.execute(sa.schema.DropSequence(sa.Sequence('pod_states_id_seq')))

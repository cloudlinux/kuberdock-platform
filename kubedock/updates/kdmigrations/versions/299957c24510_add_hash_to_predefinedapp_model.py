
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

"""Add hash to PredefinedApp model

Revision ID: 299957c24510
Revises: 33b1e3a97fb8
Create Date: 2015-10-13 18:26:06.849909

"""

# revision identifiers, used by Alembic.
revision = '299957c24510'
down_revision = '33b1e3a97fb8'

from alembic import op
import sqlalchemy as sa
from hashlib import sha1
from datetime import datetime


def upgrade():
    op.add_column('predefined_apps', sa.Column('qualifier', sa.String(40),
                  nullable=True, index=True))

    Pa = sa.Table('predefined_apps', sa.MetaData(), sa.Column('qualifier'))
    session = sa.orm.Session(bind=op.get_bind())
    for pa in session.query(Pa):
        sha = sha1()
        sha.update(str(datetime.now()))
        pa.qualifier = sha.hexdigest()
    session.commit()

    op.alter_column('predefined_apps', 'qualifier', server_default='', nullable=False)


def downgrade():
    op.drop_column('predefined_apps', 'qualifier')

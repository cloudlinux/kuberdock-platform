
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

"""Generate missed password and token for internal kuberdock user

Revision ID: 38bc6f56f2aa
Revises: 30bf03408b5e
Create Date: 2015-09-24 14:07:37.866697

"""

# revision identifiers, used by Alembic.
revision = '38bc6f56f2aa'
down_revision = '30bf03408b5e'

import logging
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker

from kubedock.users.models import User
from kubedock.settings import KUBERDOCK_INTERNAL_USER


logger = logging.getLogger(__name__)


def upgrade():
    op.add_column('pods', sa.Column('template_id', sa.Integer(), nullable=True))
    bind = op.get_bind()
    session = sessionmaker()(bind=bind)
    ku = session.query(User).filter(
        User.username == KUBERDOCK_INTERNAL_USER
    ).first()
    if not ku:
        logger.warning('Internal user not found: %s', KUBERDOCK_INTERNAL_USER)
        return

    if not ku.password_hash:
        ku.password = uuid.uuid4().hex
    ku.get_token()
    session.commit()


def downgrade():
    # There is nothing to do. We don't know if the password and token were
    # assigned by admin or by the upgrade script
    op.drop_column('pods', 'template_id')

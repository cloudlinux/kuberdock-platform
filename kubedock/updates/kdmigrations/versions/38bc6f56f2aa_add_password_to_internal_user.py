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
from sqlalchemy.orm import sessionmaker

from kubedock.users.models import User
from kubedock.settings import KUBERDOCK_INTERNAL_USER


logger = logging.getLogger(__name__)


def upgrade():
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
    pass

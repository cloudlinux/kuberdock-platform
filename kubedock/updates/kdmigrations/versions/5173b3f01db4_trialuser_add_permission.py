"""empty message

Revision ID: 5173b3f01db4
Revises: 3f771e33622a
Create Date: 2015-09-08 11:08:23.914111

"""

# revision identifiers, used by Alembic.
revision = '5173b3f01db4'
down_revision = '3f771e33622a'

from alembic import op
import sqlalchemy as sa


from kubedock.rbac.models import Role, Permission, Resource


def upgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())
    permission = session.query(Permission)\
        .join(Role, Role.id == Permission.role_id).join(Resource, Permission.resource_id == Resource.id)\
        .filter(Role.rolename == 'TrialUser').filter(Resource.name == 'pods')\
        .filter(Permission.name == 'create').one()
    permission.allow = True
    session.commit()


def downgrade():
    session = sa.orm.sessionmaker()(bind=op.get_bind())
    permission = session.query(Permission)\
        .join(Role, Role.id == Permission.role_id).join(Resource, Permission.resource_id == Resource.id)\
        .filter(Role.rolename == 'TrialUser').filter(Resource.name == 'pods')\
        .filter(Permission.name == 'create').one()
    permission.allow = False
    session.commit()

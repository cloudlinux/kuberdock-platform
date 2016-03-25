"""user.package_id: nullable=False

Revision ID: 45e4b1e232ad
Revises: 2c64986d76b9
Create Date: 2016-03-25 07:20:22.300068

"""

# revision identifiers, used by Alembic.
revision = '45e4b1e232ad'
down_revision = '2c64986d76b9'

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Session = sessionmaker()
Base = declarative_base()


class Package(Base):
    __tablename__ = 'packages'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    is_default = sa.Column(sa.Boolean, default=None)


class User(Base):
    __tablename__ = 'users'
    id = sa.Column(sa.Integer, primary_key=True, autoincrement=True, nullable=False)
    package_id = sa.Column(sa.Integer, sa.ForeignKey('packages.id'))


def upgrade():
    session = Session(bind=op.get_bind())
    default_package_id = session.query(Package.id).filter(Package.is_default).scalar()
    for user in session.query(User).filter(User.package_id.is_(None)):
        user.package_id = default_package_id
    session.commit()

    op.alter_column('users', 'package_id',
                    existing_type=sa.INTEGER(), nullable=False)


def downgrade():
    op.alter_column('users', 'package_id',
                    existing_type=sa.INTEGER(), nullable=True)

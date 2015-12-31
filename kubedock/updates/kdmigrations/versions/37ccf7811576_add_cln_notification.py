"""Add CLN_NOTIFICATION

Revision ID: 37ccf7811576
Revises: 442f26252e67
Create Date: 2015-12-31 13:56:55.531181

"""

# revision identifiers, used by Alembic.
revision = '37ccf7811576'
down_revision = '442f26252e67'

from alembic import op
import sqlalchemy as sa


Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class Notification(Base):
    __tablename__ = 'notifications'
    id = sa.Column(sa.Integer, autoincrement=True, primary_key=True, nullable=False)
    type = sa.Column(sa.String(12), nullable=False)
    message = sa.Column(sa.String(255), nullable=False, unique=True)
    description = sa.Column(sa.Text, nullable=False)


def upgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session._model_changes = False  # workaround for Flask-SQLAlchemy

    m1 = Notification(type='info',
                     message='CLN_NOTIFICATION',
                     description='')
    session.add(m1)
    session.commit()


def downgrade():
    bind = op.get_bind()
    session = Session(bind=bind)
    session._model_changes = False  # workaround for Flask-SQLAlchemy
    m = session.query(Notification).filter_by(message='CLN_NOTIFICATION').first()
    if m is not None:
        session.delete(m)
    session.commit()

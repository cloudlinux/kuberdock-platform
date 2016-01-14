"""empty message

Revision ID: 4078673e3670
Revises: 37ccf7811576
Create Date: 2016-01-14 07:38:44.472313

"""

# revision identifiers, used by Alembic.
revision = '4078673e3670'
down_revision = '37ccf7811576'

from alembic import op
import sqlalchemy as sa

Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


def upgrade():
    conn = op.get_bind()
    conn.execute("UPDATE packages SET period='month' WHERE id=0")


def downgrade():
    conn = op.get_bind()
    conn.execute("UPDATE packages SET period='hour' WHERE id=0")

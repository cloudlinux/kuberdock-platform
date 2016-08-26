"""add permissions unique constraint

Revision ID: 370f6c5fafff
Revises: 18b7f1e1988
Create Date: 2016-08-19 20:12:55.552365

"""

# revision identifiers, used by Alembic.
revision = '370f6c5fafff'
down_revision = '18b7f1e1988'

from alembic import op

COLUMNS = ['resource_id', 'role_id', 'name']
TABLE = 'rbac_permission'
CONSTRAINT_NAME = 'resource_role_name_unique'


def upgrade():
    op.create_unique_constraint(CONSTRAINT_NAME, TABLE, COLUMNS)


def downgrade():
    op.drop_constraint(CONSTRAINT_NAME, TABLE)

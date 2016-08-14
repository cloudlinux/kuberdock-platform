"""Remove user_id from predefined apps

Revision ID: 18b7f1e1988
Revises: 12963e26b673
Create Date: 2016-07-18 12:43:05.958149

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '18b7f1e1988'
down_revision = '12963e26b673'


def upgrade():
    op.drop_column('predefined_apps', 'user_id')
    op.add_column('pods', sa.Column(
        'template_plan_name', sa.String(24), nullable=True))


def downgrade():
    op.add_column('predefined_apps', sa.Column(
        'user_id',
        sa.Integer,
        sa.ForeignKey('users.id'),
        nullable=False,
        server_default='1'))
    op.drop_column('pods', 'template_plan_name')

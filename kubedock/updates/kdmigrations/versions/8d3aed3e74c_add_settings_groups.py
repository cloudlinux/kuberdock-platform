
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

"""add_settings_groups

Revision ID: 8d3aed3e74c
Revises: 12963e26b673
Create Date: 2016-08-25 18:12:06.124915

"""

# revision identifiers, used by Alembic.
revision = '8d3aed3e74c'
down_revision = '12963e26b673'

import sqlalchemy as sa
from alembic import op


def upgrade():
    conn = op.get_bind()
    op.drop_column('predefined_apps', 'user_id')
    op.add_column('pods', sa.Column(
        'template_plan_name', sa.String(24), nullable=True))
    op.create_unique_constraint('resource_role_name_unique', 'rbac_permission',
                                ['resource_id', 'role_id', 'name'])
    op.add_column(
        'system_settings', sa.Column('setting_group', sa.Text, default=''))


def downgrade():
    conn = op.get_bind()
    op.add_column('predefined_apps', sa.Column(
        'user_id',
        sa.Integer,
        sa.ForeignKey('users.id'),
        nullable=False,
        server_default='1'))
    op.drop_column('pods', 'template_plan_name')
    op.drop_constraint('resource_role_name_unique', 'rbac_permission')
    op.drop_column('system_settings', 'setting_group')

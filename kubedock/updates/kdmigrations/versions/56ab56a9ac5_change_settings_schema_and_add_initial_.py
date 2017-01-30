
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

"""change settings schema and add initial values

Revision ID: 56ab56a9ac5
Revises: 32e6666ff6d0
Create Date: 2015-12-18 14:11:16.367651

"""

# revision identifiers, used by Alembic.
revision = '56ab56a9ac5'
down_revision = '32e6666ff6d0'

from alembic import op
import sqlalchemy as sa

Session = sa.orm.sessionmaker()
Base = sa.ext.declarative.declarative_base()


class SystemSettings(Base):
    __tablename__ = 'system_settings'

    id = sa.Column(sa.Integer, primary_key=True, nullable=False)
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    value = sa.Column(sa.Text, nullable=True)
    label = sa.Column(sa.String, nullable=True)
    description = sa.Column(sa.Text, nullable=True)
    placeholder = sa.Column(sa.String, nullable=True)


def upgrade():
    session = Session(bind=op.get_bind())

    op.drop_column('system_settings', 'created')
    op.drop_column('system_settings', 'deleted')
    op.add_column('system_settings', sa.Column('label', sa.Text, nullable=True))
    op.add_column('system_settings', sa.Column('description', sa.Text, nullable=True))
    op.add_column('system_settings', sa.Column('placeholder', sa.String, nullable=True))

    billing_link = session.query(SystemSettings).filter_by(name='billing_apps_link').order_by(SystemSettings.id.desc()).first()
    if billing_link is not None:
        last = billing_link.id
        session.query(SystemSettings).filter(SystemSettings.id!=last).delete()
        billing_link.label = 'Link to billing system script'
        billing_link.description = 'Link to predefined application request processing script'
        billing_link.placeholder = 'http://whmcs.com/script.php'
    else:
        bl = SystemSettings(name='billing_apps_link',
                            label='Link to billing system script',
                            description='Link to predefined application request processing script',
                            placeholder = 'http://whmcs.com/script.php')
        session.add(bl)
    pd = SystemSettings(name='persitent_disk_max_size',
                        value='10',
                        label='Persistent disk maximum size',
                        description='maximum capacity of a user container persistent disk in GB',
                        placeholder = 'Enter value to limit PD size')
    session.add(pd)
    ms = SystemSettings(name='default_smtp_server',
                    label='Default SMTP server',
                    description='Default SMTP server',
                    placeholder = 'Default SMTP server')
    session.add(ms)
    session.commit()
    op.create_unique_constraint('uq_system_settings_name', 'system_settings', ['name'])


def downgrade():
    op.add_column('system_settings', sa.Column('created', sa.DateTime, nullable=False))
    op.add_column('system_settings', sa.Column('deleted', sa.DateTime, nullable=True))
    op.drop_column('system_settings', 'label')
    op.drop_column('system_settings', 'description')
    op.drop_column('system_settings', 'placeholder')
    op.drop_constraint('uq_system_settings_name', 'system_settings')

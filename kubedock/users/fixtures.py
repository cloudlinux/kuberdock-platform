
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

import uuid
from kubedock.rbac.models import Role
from kubedock.models import User
from kubedock.billing.models import Package
from kubedock.core import db
from kubedock.settings import KUBERDOCK_INTERNAL_USER


def add_users_and_roles(password):
    # Create all roles with users that has same name and password as role_name.
    # Useful to test permissions.
    # Delete all users from setup KuberDock. Only admin must be after install.
    # AC-228
    # for role in Role.all():
    #     u = User.filter_by(username=role.rolename).first()
    #     if u is None:
    #         u = User.create(username=role.rolename, password=role.rolename,
    #                         role=role, package=p, active=True)
    #         db.session.add(u)
    # db.session.commit()

    # Special user for convenience to type and login
    p1 = Package.filter_by(name='Standard package').first()
    r = Role.filter_by(rolename='Admin').first()
    u = User.filter_by(username='admin').first()
    if u is None:
        u = User.create(username='admin', password=password, role=r,
                        package=p1, active=True)
        db.session.add(u)
    kr = Role.filter_by(rolename='User').first()
    ku = User.filter_by(username=KUBERDOCK_INTERNAL_USER).first()
    ku_passwd = uuid.uuid4().hex
    if ku is None:
        ku = User.create(username=KUBERDOCK_INTERNAL_USER,
                         password=ku_passwd, role=kr,
                         #  package=p1, first_name='KuberDock Internal',
                         active=True)
        # generate token immediately, to use it in node creation
        ku.get_token()
        db.session.add(ku)
    db.session.commit()

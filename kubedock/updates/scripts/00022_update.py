
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

import json
from kubedock.static_pages.models import MenuItem


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add menu item Pods for the TrialUser...')
    menu_item = MenuItem.query.filter_by(name='Pods').first()
    menu_item.roles = json.dumps(json.loads(menu_item.roles) + ['TrialUser'])
    menu_item.save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove menu item Pods for the TrialUser...')
    menu_item = MenuItem.query.filter_by(name='Pods').first()
    menu_item.roles = json.dumps([role for role in json.loads(menu_item.roles)
                                  if role != 'TrialUser'])
    menu_item.save()

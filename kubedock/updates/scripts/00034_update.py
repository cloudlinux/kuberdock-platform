
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

from kubedock.core import db

from kubedock.static_pages.models import Menu, MenuItem


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add "Predefined Applications" menu item...')
    menu = Menu.query.filter_by(region=Menu.REGION_NAVBAR).first()
    menu_item = MenuItem(name='Predefined Applications', menu=menu, ordering=2,
                         path='/predefined-apps/', roles=json.dumps(['Admin']))
    db.session.add(menu_item)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove "Predefined Applications" menu item...')
    menu_item = MenuItem.query.filter_by(name='Predefined Applications').first()
    db.session.delete(menu_item)
    db.session.commit()

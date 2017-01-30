
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

from kubedock.billing.models import Kube
from kubedock.core import db

OLD_NAME = "Standard kube"
NEW_NAME = "Standard"


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Rename `Standard kube` to `Standard`')
    kube = db.session.query(Kube).filter(Kube.name == OLD_NAME).first()
    if kube:
        kube.name = NEW_NAME
        db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    upd.print_log('Rename `Standard` to `Standard kube` back')
    kube = db.session.query(Kube).filter(Kube.name == NEW_NAME).first()
    if kube:
        kube.name = OLD_NAME
        db.session.commit()

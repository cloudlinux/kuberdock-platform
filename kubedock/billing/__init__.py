
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

from .models import Kube, Package, ExtraTax, PackageKube
from kubedock.system_settings.models import SystemSettings


def kubes_to_limits(count, kube_type):
    kube = Kube.query.get(kube_type)

    resources = {
        'cpu': '{0}'.format(count * kube.cpu),
        'memory': int(count * kube.memory * 1024 * 1024)    # was in MB
    }
    return {'resources': {
        'requires': resources,
        'limits': resources,
    }}


def repr_limits(count, kube_type):
    kube = Kube.query.get(kube_type)

    cpu = '{0} {1}'.format(count * kube.cpu, kube.cpu_units)
    memory = '{0} {1}'.format(count * kube.memory, kube.memory_units)

    return {'cpu': cpu, 'memory': memory}


def has_billing():
    billing_type = SystemSettings.get_by_name('billing_type').lower()
    if billing_type == 'no billing':
        return False
    return True

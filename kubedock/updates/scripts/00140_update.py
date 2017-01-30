
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
import os
import shutil
from collections import defaultdict

from fabric.api import hide, put, run, settings
from fabric.exceptions import CommandTimeout, NetworkError
from kubedock.billing.models import Kube
from kubedock.core import db
from kubedock.kapi import pd_utils, pstorage
from kubedock.kapi.helpers import KubeQuery, get_pod_config, replace_pod_config
from kubedock.kapi.podcollection import PodCollection
from kubedock.nodes.models import Node
from kubedock.pods.models import PersistentDisk, PersistentDiskStatuses, Pod
from kubedock.rbac.fixtures import Permission, Resource, add_permissions
from kubedock.settings import AWS, CEPH, NODE_LOCAL_STORAGE_PREFIX
from kubedock.static_pages.fixtures import (Menu, MenuItem, MenuItemRole,
                                            generate_menu)
from kubedock.system_settings.models import SystemSettings
from kubedock.updates.helpers import (close_all_sessions, downgrade_db,
                                      install_package, reboot_node,
                                      start_service, stop_service, upgrade_db)
from kubedock.utils import randstr, NODE_STATUSES

u124_old = '/index.txt'
u124_new = '/var/lib/kuberdock/k8s2etcd_resourceVersion'
u124_service_name = 'kuberdock-k8s2etcd'

u132_old_version = "3.10.0-229.11.1.el7.centos"

u133_PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/'

u138_PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock'
u138_SCRIPT_DIR = '/var/lib/kuberdock/scripts'
u138_FSLIMIT_PATH = os.path.join(u138_SCRIPT_DIR, 'fslimit.py')


def upgrade_localstorage_paths(upd):
    upd.print_log('Update local storages on nodes...')

    node_to_pds = defaultdict(list)
    pod_to_pds = defaultdict(list)
    for pd in db.session.query(PersistentDisk).filter(
                    PersistentDisk.state != PersistentDiskStatuses.TODELETE):
        node_to_pds[pd.node_id].append(pd)
        if pd.pod_id:
            pod_to_pds[pd.pod_id].append(pd)
    for node_id, pd_list in node_to_pds.iteritems():
        # move PD on each node to new location
        if node_id:
            node = Node.get_by_id(node_id)
        else:
            node = None

        path_pairs = []
        for pd in pd_list:
            old_path = os.path.join(NODE_LOCAL_STORAGE_PREFIX, pd.drive_name)
            pd.drive_name = pd_utils.compose_pdname(pd.name, pd.owner_id)
            new_path = pstorage.LocalStorage.get_full_drive_path(pd.drive_name)
            path_pairs.append([old_path, new_path, pd.size])

        timeout = 60
        if node is not None:
            with settings(hide(NODE_STATUSES.running, 'warnings', 'stdout', 'stderr'),
                          host_string=node.hostname, warn_only=True):
                try:
                    put('/var/opt/kuberdock/node_network_plugin.py',
                        os.path.join(u138_PLUGIN_DIR, 'kuberdock.py'))
                    put('/var/opt/kuberdock/fslimit.py', u138_FSLIMIT_PATH)
                    for old_path, new_path, size in path_pairs:
                        result = run('test -d {}'.format(old_path),
                                     timeout=timeout)
                        if result.return_code != 0:
                            continue
                        run('[ -d {0} ] || mkdir -p {0}'.format(
                            os.path.dirname(new_path)),
                            timeout=timeout)
                        run('mv {} {}'.format(old_path, new_path),
                            timeout=timeout)
                        run('/usr/bin/env python2 {} storage {}={}g'.format(
                            u138_FSLIMIT_PATH, new_path, size))
                except (CommandTimeout, NetworkError):
                    upd.print_log(
                        'Node {} is unavailable, skip moving of localstorages'
                    )
        for pd in pd_list:
            pstorage.update_pods_volumes(pd)

    # Update RC and running pods
    for pod_id in pod_to_pds:
        pod = Pod.query.filter(Pod.id == pod_id).first()
        config = pod.get_dbconfig()
        volumes = config.get('volumes', [])
        annotations = [vol.pop('annotation') for vol in volumes]
        res = PodCollection().patch_running_pod(
            pod_id,
            {
                'metadata': {
                    'annotations': {
                        'kuberdock-volume-annotations': json.dumps(annotations)
                    }
                },
                'spec': {
                    'volumes': volumes
                },
            },
            replace_lists=True,
            restart=True
        )
        res = res or {}
        upd.print_log('Updated pod: {}'.format(res.get('name', 'Unknown')))

    db.session.commit()


def upgrade(upd, with_testing, *args, **kwargs):
    upgrade_db()

    # === 00124_update.py ===
    # Move index file of k8s2etcd service from / to /var/lib/kuberdock
    try:
        stop_service(u124_service_name)
        if os.path.isfile(u124_old) and not os.path.isfile(u124_new):
            shutil.move(u124_old, u124_new)
    finally:
        start_service(u124_service_name)

    # === 00126_update.py ===

    pod_collection = PodCollection()
    for pod_dict in pod_collection.get(as_json=False):
        pod = pod_collection._get_by_id(pod_dict['id'])
        db_config = get_pod_config(pod.id)
        cluster_ip = db_config.pop('clusterIP', None)
        if cluster_ip is None:
            service_name = db_config.get('service')
            if service_name is None:
                continue
            namespace = db_config.get('namespace') or pod.id
            service = KubeQuery().get(['services', service_name],
                                      ns=namespace)
            cluster_ip = service.get('spec', {}).get('clusterIP')
            if cluster_ip is not None:
                db_config['podIP'] = cluster_ip
        replace_pod_config(pod, db_config)

    # === 00127_update.py ===

    upd.print_log('Upgrading menu...')
    MenuItemRole.query.delete()
    MenuItem.query.delete()
    Menu.query.delete()
    generate_menu()

    # === 00130_update.py ===

    upd.print_log('Update permissions...')
    Permission.query.delete()
    Resource.query.delete()
    add_permissions()
    db.session.commit()

    # === 00135_update.py ===
    # upd.print_log('Changing session_data schema...')
    # upgrade_db(revision='220dacf65cba')


    # === 00137_update.py ===
    upd.print_log('Upgrading db...')
    # upgrade_db(revision='3c832810a33c')
    upd.print_log('Raise max kubes to 64')
    max_kubes = 'max_kubes_per_container'
    old_value = SystemSettings.get_by_name(max_kubes)
    if old_value == '10':
        SystemSettings.set_by_name(max_kubes, 64)
    upd.print_log('Update kubes')
    small = Kube.get_by_name('Small')
    standard = Kube.get_by_name('Standard')
    if small:
        small.cpu = 0.12
        small.name = 'Tiny'
        small.memory = 64
        if small.is_default and standard:
            small.is_default = False
            standard.is_default = True
        small.save()
    if standard:
        standard.cpu = 0.25
        standard.memory = 128
        standard.save()
    high = Kube.get_by_name('High memory')
    if high:
        high.cpu = 0.25
        high.memory = 256
        high.disk_space = 3
        high.save()

    # === 00138_update.py ===

    if not (CEPH or AWS):
        upgrade_localstorage_paths(upd)

    # === added later ===

    secret_key = SystemSettings.query.filter(
        SystemSettings.name == 'sso_secret_key').first()
    if not secret_key.value:
        secret_key.value = randstr(16)
    secret_key.description = (
    'Used for Single sign-on. Must be shared between '
    'Kuberdock and billing system or other 3rd party '
    'application.')
    db.session.commit()

    upd.print_log('Close all sessions...')
    close_all_sessions()


def downgrade(upd, *args, **kwars):
    # === 00137_update.py ===

    # upd.print_log('Downgrading db...')
    # downgrade_db(revision='220dacf65cba')


    # === 00135_update.py ===

    upd.print_log('Downgrading db...')
    downgrade_db(revision='45e4b1e232ad')

    # === 00124_update.py ===

    try:
        stop_service(u124_service_name)
        if os.path.isfile(u124_new) and not os.path.isfile(u124_old):
            shutil.move(u124_new, u124_old)
    finally:
        start_service(u124_service_name)


def upgrade_node(upd, with_testing, *args, **kwargs):
    run('yum --enablerepo=kube,kube-testing clean metadata')

    # === 00132_update.py ===

    yum_base_no_kube = 'yum install --disablerepo=kube -y '

    run(yum_base_no_kube + 'kernel')
    run(yum_base_no_kube + 'kernel-tools')
    run(yum_base_no_kube + 'kernel-tools-libs')
    run(yum_base_no_kube + 'kernel-headers')
    run(yum_base_no_kube + 'kernel-devel')

    run('rpm -e -v --nodeps kernel-' + u132_old_version)
    run('yum remove -y kernel-tools-' + u132_old_version)
    run('yum remove -y kernel-tools-libs-' + u132_old_version)
    run('yum remove -y kernel-headers-' + u132_old_version)
    run('yum remove -y kernel-devel-' + u132_old_version)
    # reboot_node(upd)  # moved to the end


    # === 00133_update.py ===

    put('/var/opt/kuberdock/node_network_plugin.sh',
        u133_PLUGIN_DIR + 'kuberdock')
    put('/var/opt/kuberdock/node_network_plugin.py',
        u133_PLUGIN_DIR + 'kuberdock.py')
    run('systemctl restart kuberdock-watcher')

    # === 00138_update.py ===

    put('/var/opt/kuberdock/node_network_plugin.py',
        os.path.join(u138_PLUGIN_DIR, 'kuberdock.py'))
    put('/var/opt/kuberdock/fslimit.py',
        os.path.join(u138_SCRIPT_DIR, 'fslimit.py'))

    # moved from 00132_update.py
    reboot_node(upd)


def downgrade_node(upd, with_testing, exception, *args, **kwargs):
    # === 00132_update.py ===

    install_package('kernel-' + u132_old_version, action='upgrade')
    install_package('kernel-tools-' + u132_old_version, action='upgrade')
    install_package('kernel-tools-libs-' + u132_old_version, action='upgrade')
    install_package('kernel-headers-' + u132_old_version, action='upgrade')
    install_package('kernel-devel-' + u132_old_version, action='upgrade')
    reboot_node(upd)

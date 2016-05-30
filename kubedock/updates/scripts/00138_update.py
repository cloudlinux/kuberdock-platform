import os
from itertools import izip
from collections import defaultdict
import json

from fabric.api import run, settings, env, hide, put
from fabric.exceptions import CommandTimeout, NetworkError

from kubedock.settings import CEPH, AWS, NODE_LOCAL_STORAGE_PREFIX
from kubedock.kapi import pstorage, pd_utils, podcollection
from kubedock.pods.models import PersistentDisk, PersistentDiskStatuses, Pod
from kubedock.nodes.models import Node

from kubedock.updates import helpers
from kubedock.core import ConnectionPool, db

PLUGIN_DIR = '/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock'
SCRIPT_DIR = '/var/lib/kuberdock/scripts'
FSLIMIT_PATH = os.path.join(SCRIPT_DIR, 'fslimit.py')


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
            with settings(hide('running', 'warnings', 'stdout', 'stderr'),
                          host_string=node.hostname, warn_only=True):
                try:
                    put('/var/opt/kuberdock/node_network_plugin.py',
                        os.path.join(PLUGIN_DIR, 'kuberdock.py'))
                    put('/var/opt/kuberdock/fslimit.py', FSLIMIT_PATH)
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
                                FSLIMIT_PATH, new_path, size))
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
        res = podcollection.PodCollection().patch_running_pod(
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
    if not (CEPH or AWS):
        upgrade_localstorage_paths(upd)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Nothing to downgrade')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    put('/var/opt/kuberdock/node_network_plugin.py',
        os.path.join(PLUGIN_DIR, 'kuberdock.py'))
    put('/var/opt/kuberdock/fslimit.py',
        os.path.join(SCRIPT_DIR, 'fslimit.py'))


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    pass

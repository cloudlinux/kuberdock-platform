import os
from kubedock.updates import helpers
from fabric.api import run, put, get
from kubedock.kapi.podcollection import PodCollection
from kubedock.billing.models import Kube
from kubedock.utils import POD_STATUSES

SERVICE_FILE = \
"""
[Unit]
Description=KuberDock kubernetes to etcd events middleware
Before=kube-apiserver.service

[Service]
ExecStart=/usr/bin/env python2 /var/opt/kuberdock/k8s2etcd.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
EOF
"""

K8S_API_SERVICE_FILE = \
"""
[Unit]
Description=Kubernetes API Server
Documentation=https://github.com/GoogleCloudPlatform/kubernetes
After=etcd.service

[Service]
EnvironmentFile=-/etc/kubernetes/config
EnvironmentFile=-/etc/kubernetes/apiserver
User=kube
ExecStart=/usr/bin/kube-apiserver \
	    $KUBE_LOGTOSTDERR \
	    $KUBE_LOG_LEVEL \
	    $KUBE_ETCD_SERVERS \
	    $KUBE_API_ADDRESS \
	    $KUBE_API_PORT \
	    $KUBELET_PORT \
	    $KUBE_ALLOW_PRIV \
	    $KUBE_SERVICE_ADDRESSES \
	    $KUBE_ADMISSION_CONTROL \
	    $KUBE_API_ARGS
Restart=on-failure
Type=notify
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF
"""

KUBE_API_SERVER_PATH = '/etc/kubernetes/apiserver'
KUBE_API_SERVER_ARG = 'KUBE_API_ARGS'
KUBE_API_WATCHCACHE_DISABLE = ' --watch-cache=false'

KUBELET_PATH = '/etc/kubernetes/kubelet'
KUBELET_ARG = 'KUBELET_ARGS'
KUBELET_CPUCFS_ENABLE = ' --cpu-cfs-quota=true'
KUBELET_TEMP_PATH = '/tmp/kubelet'

ETCD_SERVICE = 'etcd.service'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update kubes to hard limits')
    internal = Kube.get_by_name('Internal service')
    if internal:
        internal.cpu = 0.05
        internal.save()
    small = Kube.get_by_name('Small')
    if small:
        small.cpu = 0.05
        small.save()
    standard = Kube.get_by_name('Standard')
    if standard:
        standard.cpu = 0.25
        standard.save()
    high = Kube.get_by_name('High memory')
    if high:
        high.cpu = 0.5
        high.save()
    upd.print_log('Setup k8s2etcd middleware service')
    upd.print_log(
        helpers.local(
            "cat > /etc/systemd/system/kuberdock-k8s2etcd.service << 'EOF' {0}"
            .format(SERVICE_FILE))
    )

    helpers.local('systemctl daemon-reload')
    upd.print_log(helpers.local('systemctl reenable kuberdock-k8s2etcd'))
    upd.print_log(helpers.local('systemctl restart kuberdock-k8s2etcd'))

    helpers.install_package('kubernetes-master-1.1.3', with_testing)
    upd.print_log('Add after etcd.service to kube-apiserver service file')
    upd.print_log(
        helpers.local(
            "cat > /etc/systemd/system/kube-apiserver.service << 'EOF' {0}"
            .format(K8S_API_SERVICE_FILE))
    )
    upd.print_log('Turn off watch-cache in kube_apiserver')
    lines = []
    with open(KUBE_API_SERVER_PATH) as f:
        lines = f.readlines()
    with open(KUBE_API_SERVER_PATH, 'w+') as f:
        for line in lines:
            if (KUBE_API_SERVER_ARG in line and
                not KUBE_API_WATCHCACHE_DISABLE in line):
                s = line.split('"')
                s[1] += KUBE_API_WATCHCACHE_DISABLE
                line = '"'.join(s)
            f.write(line)
    helpers.restart_master_kubernetes(with_enable=True)

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    helpers.remote_install('kubernetes-node-1.1.3', with_testing)
    upd.print_log("Turn on cpu-cfs-quota in kubelet")

    get(KUBELET_PATH, KUBELET_TEMP_PATH)
    lines = []
    with open(KUBELET_TEMP_PATH) as f:
        lines = f.readlines()
    with open(KUBELET_TEMP_PATH, 'w+') as f:
        for line in lines:
            if KUBELET_ARG in line and not KUBELET_CPUCFS_ENABLE in KUBELET_ARG:
                s = line.split('"')
                s[1] += KUBELET_CPUCFS_ENABLE
                line = '"'.join(s)
            f.write(line)
    put(KUBELET_TEMP_PATH, KUBELET_PATH)
    os.remove(KUBELET_TEMP_PATH)
    helpers.restart_node_kubernetes(with_enable=True)
    upd.print_log("Restart pods to apply new limits")
    pc = PodCollection()
    pods = pc.get(as_json=False)
    for pod in pods:
        if pod['status'] == POD_STATUSES.running:
            pc.update_container(pod['id'], None)


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade_node provided')

def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')

from kubedock.updates import helpers
from fabric.api import local, run

KUBELET_CONFIG_FILE = '/etc/kubernetes/kubelet'

KPROXY_CONF = """\
[Unit]
After=network-online.target

[Service]
Restart=always
RestartSec=5s\
"""
KPROXY_SERVICE_DIR = "/etc/systemd/system/kube-proxy.service.d"


def _update_proxy_service(upd, func):
    upd.print_log('Enabling restart=always for kube-proxy.service')
    func('mkdir -p ' + KPROXY_SERVICE_DIR)
    func('echo -e "' + KPROXY_CONF + '" > ' + KPROXY_SERVICE_DIR + "/restart.conf")
    func('systemctl daemon-reload')
    func('systemctl restart kube-proxy')


def upgrade(upd, *args, **kwargs):
    _update_proxy_service(upd, local)


def downgrade(*args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, node_ip, *args, **kwargs):
    upd.print_log('Update kubelet config')
    helpers.update_remote_config_file(
        KUBELET_CONFIG_FILE,
        {
            'KUBELET_ARGS': {
                '--node-ip=': node_ip
            }
        }
    )
    helpers.run('systemctl restart kubelet')
    # that's enough. IP address will be changed by kubernetes if needed

    _update_proxy_service(upd, run)


def downgrade_node(*args, **kwargs):
    pass

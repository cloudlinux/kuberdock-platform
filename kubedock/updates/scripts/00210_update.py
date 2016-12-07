from kubedock.updates import helpers

KUBELET_CONFIG_FILE = '/etc/kubernetes/kubelet'


def upgrade(upd, *args, **kwargs):
    pass


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


def downgrade_node(*args, **kwargs):
    pass

from fabric.api import run, put

from kubedock.updates import helpers

PLUGIN_DIR = "/usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/"


SERVICE_FILE = \
"""
[Unit]
Description=KuberDock Network Plugin watcher
After=flanneld.service
Requires=flanneld.service

[Service]
ExecStart=/usr/bin/env python2 /usr/libexec/kubernetes/kubelet-plugins/net/exec/kuberdock/kuberdock.py watch

[Install]
WantedBy=multi-user.target
EOF
"""


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Setup network plugin:')

    upd.print_log('Install packages...')
    upd.print_log(helpers.remote_install('python-requests', with_testing))
    upd.print_log(helpers.remote_install('python-ipaddress', with_testing))
    upd.print_log(helpers.remote_install('ipset', with_testing))

    upd.print_log(run("""sed -i '/^KUBELET_ARGS/ {s|"\(.*\) --network-plugin=kuberdock"|"\\1"|}' /etc/kubernetes/kubelet"""))
    upd.print_log(run("""sed -i '/^KUBELET_ARGS/ {s|"\(.*\) --register-node=false"|"\\1 --register-node=false --network-plugin=kuberdock"|}' /etc/kubernetes/kubelet"""))

    upd.print_log(run("mkdir -p {0}".format(PLUGIN_DIR)))
    upd.print_log(put('/var/opt/kuberdock/node_network_plugin.sh',
                      PLUGIN_DIR + 'kuberdock',
                      mode=0755))
    upd.print_log(put('/var/opt/kuberdock/node_network_plugin.py',
                      PLUGIN_DIR + 'kuberdock.py',
                      mode=0755))
    upd.print_log(run('chmod +x {0}'.format(PLUGIN_DIR + 'kuberdock')))

    upd.print_log(
        run("cat > /etc/systemd/system/kuberdock-watcher.service << 'EOF' {0}"
            .format(SERVICE_FILE))
    )

    run('systemctl daemon-reload')
    upd.print_log(run('systemctl reenable kuberdock-watcher'))

    upd.print_log('Rebooting node...')
    run('(sleep 2; reboot) &', pty=False)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')

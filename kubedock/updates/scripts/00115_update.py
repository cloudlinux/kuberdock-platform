from fabric.api import run

from kubedock.updates import helpers


DOCKER_SERVICE_FILE = '/etc/systemd/system/docker.service'
DOCKER_SERVICE = r'''[Unit]
Description=Docker Application Container Engine
Documentation=http://docs.docker.com
After=network.target

[Service]
Type=notify
EnvironmentFile=-/etc/sysconfig/docker
EnvironmentFile=-/etc/sysconfig/docker-storage
EnvironmentFile=-/etc/sysconfig/docker-network
Environment=GOTRACEBACK=crash
ExecStart=/usr/bin/docker daemon $OPTIONS \\
          $DOCKER_STORAGE_OPTIONS \\
          $DOCKER_NETWORK_OPTIONS \\
          $ADD_REGISTRY \\
          $BLOCK_REGISTRY \\
          $INSECURE_REGISTRY
LimitNOFILE=1048576
LimitNPROC=1048576
LimitCORE=infinity
MountFlags=slave
TimeoutStartSec=1min
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target'''
DOCKER_SERVICE_DIR = '/etc/systemd/system/docker.service.d'
FLANNEL_CONF_FILE = '/etc/systemd/system/docker.service.d/flannel.conf'
FLANNEL_CONF = '''[Service]
EnvironmentFile=/run/flannel/docker'''


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Updating flannel and docker services...')
    upd.print_log(
        run("echo '{0}' > '{1}'".format(DOCKER_SERVICE, DOCKER_SERVICE_FILE))
    )
    upd.print_log(run('mkdir -p {0}'.format(DOCKER_SERVICE_DIR)))
    upd.print_log(
        run("echo '{0}' > '{1}'".format(FLANNEL_CONF, FLANNEL_CONF_FILE))
    )
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl reenable docker'))
    upd.print_log(run('systemctl reenable flanneld'))

    # TODO: This check and node reboot should be placed at the end of merged update script
    check = run(
        'source /run/flannel/docker'
        ' && '
        'grep "$DOCKER_NETWORK_OPTIONS" <<< "$(ps ax)"'
        ' > /dev/null'
    )

    if check.failed:
        upd.print_log('Node need to be rebooted')
        helpers.reboot_node(upd)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Removing custom flannel and docker services...')
    upd.print_log(run("rm -rf '{0}'".format(DOCKER_SERVICE_DIR)))
    upd.print_log(run("rm -rf '{0}'".format(DOCKER_SERVICE_FILE)))
    upd.print_log(run('systemctl daemon-reload'))
    upd.print_log(run('systemctl reenable docker'))
    upd.print_log(run('systemctl reenable flanneld'))

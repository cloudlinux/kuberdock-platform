"""AC-5478 Bump Docker Epoch"""

from kubedock.updates import helpers


DOCKER_VERSION = '1.12.1-5.el7'
DOCKER = 'docker-{ver}'.format(ver=DOCKER_VERSION)
DOCKER_SELINUX = 'docker-selinux-{ver}'.format(ver=DOCKER_VERSION)


def _update_00213_upgrade_node(upd, with_testing):
    upd.print_log('Updating Docker packages...')
    helpers.remote_install(DOCKER_SELINUX, with_testing)
    helpers.remote_install(DOCKER, with_testing)


def upgrade(upd, with_testing, *args, **kwargs):
    # Docker on master upgraded via KuberDock package dependency
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _update_00213_upgrade_node(upd, with_testing)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


from kubedock.updates import helpers

DOCKER_VERSION = '1.8.2-11.el7'
DOCKER = 'docker-{ver}'.format(ver=DOCKER_VERSION)
SELINUX = 'docker-selinux-{ver}'.format(ver=DOCKER_VERSION)

OLD_DOCKER_VERSION = '1.8.2-10.el7'
OLD_DOCKER = 'docker-{ver}'.format(ver=OLD_DOCKER_VERSION)
OLD_SELINUX = 'docker-selinux-{ver}'.format(ver=OLD_DOCKER_VERSION)


def _upgrade_docker(with_testing):
    helpers.remote_install(SELINUX, with_testing)
    helpers.remote_install(DOCKER, with_testing)


def _downgrade_docker(with_testing):
    helpers.remote_install(" ".join([OLD_DOCKER, OLD_SELINUX]),
                           with_testing, action='downgrade')


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_docker(with_testing)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    _downgrade_docker(with_testing)
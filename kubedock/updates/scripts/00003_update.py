from kubedock.updates import helpers
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    helpers.install_package('kuberdock', with_testing)
    helpers.upgrade_db(revision='head')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # do not output to stdout because of unicode decoding exception
    run('rpm --nodeps -e docker')
    run('rm -rf /var/lib/docker')
    run('yum install kernel kernel-headers kernel-tools kernel-tools-libs docker-1.6.2 docker-selinux-1.6.2 --disablerepo=extras --enablerepo=kube-testing -y')
    run('rm -f /etc/sysconfig/docker-storage.rpmsave')
    run("sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage")
    run("reboot")


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    pass

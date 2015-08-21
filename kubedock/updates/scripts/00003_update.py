from fabric.api import run

def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    # do not output to stdout because of unicode decoding exception
    run('rpm --nodeps -e docker docker-selinux')
    run('rm -rf /var/lib/docker')
    run('yum install kernel kernel-headers kernel-tools '
        'kernel-tools-libs docker-1.6.2 docker-selinux-1.6.2 '
        '--disablerepo=extras --disablerepo=updates '
        '--enablerepo={0} -y'.format('kube-testing' if with_testing else 'kube'))
    run('rm -f /etc/sysconfig/docker-storage.rpmsave')
    run("sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS="
        "--storage-driver=overlay' /etc/sysconfig/docker-storage")
    run("reboot")


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
   pass

import os

from kubedock.updates import helpers
from fabric.api import run
from alembic import command
from alembic.config import Config

base, _ = os.path.split(os.path.dirname(__file__))

location = os.path.join(base, 'kdmigrations')
conffile = os.path.join(location, 'alembic.ini')

acfg=Config(conffile)
acfg.set_main_option('script_location',location)

from kubedock.api import create_app

def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log("Upgrading kuberdock...")
    helpers.install_package('kuberdock', with_testing)
    app = create_app()
    with app.app_context():
        command.upgrade(acfg, '144bf08f16b')

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    app = create_app()
    with app.app_context():
        command.downgrade(acfg,'base')

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Replacing node kernel with new one...')
    # do not output to stdout because of unicode decoding exception
    run('rpm --nodeps -e docker')
    run('rm -rf /var/lib/docker')
    run('yum install kernel kernel-headers kernel-tools kernel-tools-libs docker-1.6.2 docker-selinux-1.6.2 --disablerepo=extras --enablerepo=kube-testing')
    run('rm -f /etc/sysconfig/docker-storage.rpmsave')
    run("sed -i '/^DOCKER_STORAGE_OPTIONS=/c\DOCKER_STORAGE_OPTIONS=--storage-driver=overlay' /etc/sysconfig/docker-storage")

def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
   pass
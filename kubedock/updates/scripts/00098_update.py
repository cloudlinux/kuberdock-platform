from shutil import copyfile
from fabric.api import local

def upgrade(upd, with_testing, *args, **kwargs):
    copyfile('/var/opt/kuberdock/conf/sudoers-nginx.conf', '/etc/sudoers.d/nginx')
    local('chown nginx:nginx /etc/nginx/conf.d/shared-kubernetes.conf')
    local('chown nginx:nginx /etc/nginx/conf.d/shared-etcd.conf')

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass

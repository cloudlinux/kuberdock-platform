from shutil import copyfile, copystat
from kubedock.updates import helpers

nginx_path = '/etc/nginx/nginx.conf'
kd_path = '/etc/nginx/conf.d/kuberdock-ssl.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Update nginx config...')

    copyfile(nginx_path, nginx_path + '.disabled')
    copystat(nginx_path, nginx_path + '.disabled')
    copyfile(kd_path, kd_path + '.disabled')
    copystat(kd_path, kd_path + '.disabled')

    copyfile('/var/opt/kuberdock/conf/nginx.conf', nginx_path)
    copyfile('/var/opt/kuberdock/conf/kuberdock-ssl.conf', kd_path)
    helpers.restart_service('nginx')


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Rollback nginx config...')
    copyfile(nginx_path + '.disabled', nginx_path)
    copyfile(kd_path + '.disabled', kd_path)
    helpers.restart_service('nginx')

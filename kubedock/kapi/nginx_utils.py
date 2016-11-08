import subprocess

import nginx

from flask import current_app
from ..nodes.models import RegisteredHost

files = ['/etc/nginx/conf.d/shared-kubernetes.conf',
         '/etc/nginx/conf.d/shared-etcd.conf']
deny_all = nginx.Key('deny', 'all')


def update_allowed(accept_ips, conf):
    for server in conf.filter('Server'):
        for location in server.filter('Location'):
            if not any([key.name == 'return' and
                        key.value.startswith(('403', '404', '418'))
                        for key in location.keys]):
                for key in location.keys:
                    if key.name in ('allow', 'deny'):
                        location.remove(key)
                for ip in accept_ips:
                    location.add(nginx.Key('allow', ip))
                location.add(deny_all)


def update_nginx_proxy_restriction():
    accept_ips = [h for h, in RegisteredHost.query.values(RegisteredHost.host)]
    current_app.logger.debug('UPDATE NGINX PROXY FOR RHOSTS: {}'
                             .format(accept_ips))
    for filename in files:
        conf = nginx.loadf(filename)
        update_allowed(accept_ips, conf)
        nginx.dumpf(conf, filename)
    # Because only root can reload daemons we've created special wrapper
    # and configure sudo to allow required action
    subprocess.call('sudo /var/opt/kuberdock/nginx_reload.sh', shell=True)

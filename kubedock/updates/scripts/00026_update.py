from collections import defaultdict

from kubedock.billing.models import Kube
from kubedock.core import db, ssh_connect
from kubedock.kapi.podcollection import PodCollection
from kubedock.users.models import User


def _set_limits():
    spaces = dict((i, (s, u)) for i, s, u in Kube.query.values(
        Kube.id, Kube.disk_space, Kube.disk_space_units))

    hosts = defaultdict(list)
    for user in User.query:
        for pod in PodCollection(user).get(as_json=False):
            for container in pod['containers']:
                if 'containerID' not in container:
                    continue
                space, unit = spaces.get(pod['kube_type'], (0, 'GB'))
                disk_space = space * container['kubes']
                disk_space_unit = unit[0].lower() if unit else ''
                if disk_space_unit not in ('', 'k', 'm', 'g', 't'):
                    disk_space_unit = ''
                disk_space_str = '{0}{1}'.format(disk_space, disk_space_unit)
                hosts[pod['host']].append('='.join((container['containerID'],
                                          disk_space_str)))

    for host, limits in hosts.items():
        ssh, error = ssh_connect(host)
        if error:
            raise IOError(error)

        _, o, e = ssh.exec_command(
            'python /var/lib/kuberdock/scripts/fslimit.py {0}'.format(
                ' '.join(limits))
        )
        exit_status = o.channel.recv_exit_status()
        ssh.close()
        if exit_status > 0:
            raise IOError('Error fslimit.py with exit status {0}'.format(
                exit_status))


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Convert Kube.disk_space to GB...')
    for kube in Kube.query:
        if kube.disk_space_units == 'MB':
            disk_space = kube.disk_space / 2 ** 10
            kube.disk_space = disk_space if disk_space > 0 else 1
            kube.disk_space_units = 'GB'
    db.session.commit()
    _set_limits()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Convert Kube.disk_space to MB...')
    for kube in Kube.query:
        if kube.disk_space_units == 'GB':
            kube.disk_space *= 2 ** 10
            kube.disk_space_units = 'MB'
    db.session.commit()

from fabric.api import put, run

from kubedock.billing.models import Kube
from kubedock.kapi.podcollection import PodCollection
from kubedock.users.models import User


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Update fslimit.py script...')
    upd.print_log(put('/var/opt/kuberdock/fslimit.py',
                      '/var/lib/kuberdock/scripts/fslimit.py {0}',
                      mode=0755))

    upd.print_log('Update FS limits on nodes...')

    upd.print_log(run('rm -f /etc/{projects,projid}'))

    spaces = dict((i, (s, u)) for i, s, u in Kube.query.values(
        Kube.id, Kube.disk_space, Kube.disk_space_units))

    limits = []
    for user in User.query:
        for pod in PodCollection(user).get(as_json=False):
            if pod.get('host') != env.host_string:
                continue
            for container in pod['containers']:
                container_id = container['containerID']
                if container_id == container['name']:
                    continue
                space, unit = spaces.get(pod['kube_type'], (0, 'GB'))
                disk_space = space * container['kubes']
                disk_space_units = unit[0].lower() if unit else ''
                if disk_space_units not in ('', 'k', 'm', 'g', 't'):
                    disk_space_units = ''
                limits.append([container_id, disk_space, disk_space_units])

    if not limits:
        return

    lim_str = ' '.join(['{0}={1}{2}'.format(c, s, u) for c, s, u in limits])
    upd.print_log(
        run('python /var/lib/kuberdock/scripts/fslimit.py {0}'.format(lim_str))
    )


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade_node provided')

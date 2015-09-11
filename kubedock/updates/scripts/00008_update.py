import json

from kubedock.pods.models import Pod
from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='5173b3f01db4')

    upd.print_log('Clear pod configs from old api...')
    for pod in Pod.query.all():
        conf = json.loads(pod.config)
        try:
            del conf['save_only']
        except KeyError:
            pass
        pod.config = json.dumps(conf)
    upd.print_log('Done.')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db()

from fabric.api import run, put
from sqlalchemy import Table

from kubedock.core import db
from kubedock.nodes.models import NodeAction
from kubedock.system_settings.models import SystemSettings


# see also kubedock/system_settings/fixtures.py
CPU_MULTIPLIER = '8'
MEMORY_MULTIPLIER = '4'


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add system settings for CPU and Memory multipliers')
    db.session.add_all([
        SystemSettings(
            name='cpu_multiplier', value=CPU_MULTIPLIER,
            label='CPU multiplier',
            description='Cluster CPU multiplier',
            placeholder='Enter value for CPU multiplier'),
        SystemSettings(
            name='memory_multiplier', value=MEMORY_MULTIPLIER,
            label='Memory multiplier',
            description='Cluster Memory multiplier',
            placeholder='Enter value for Memory multiplier'),
    ])

    upd.print_log('Create table for NodeAction model if not exists')
    NodeAction.__table__.create(bind=db.engine, checkfirst=True)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove system settings for CPU and Memory multipliers')
    for name in ('cpu_multiplier', 'memory_multiplier'):
        entry = SystemSettings.query.filter_by(name=name).first()
        if entry is not None:
            db.session.delete(entry)

    upd.print_log('Drop table "node_actions" if exists')
    table = Table('node_actions', db.metadata)
    table.drop(bind=db.engine, checkfirst=True)
    db.session.commit()


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Copy kubelet_args.py...')
    put('/var/opt/kuberdock/kubelet_args.py',
        '/var/lib/kuberdock/scripts/kubelet_args.py',
        mode=0755)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Remove kubelet_args.py...')
    run('rm -f /var/lib/kuberdock/scripts/kubelet_args.py')

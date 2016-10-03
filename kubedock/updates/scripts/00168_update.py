import os
from ConfigParser import ConfigParser

from fabric.operations import run

from kubedock import settings

KUBERDOCK_MAIN_CONFIG = '/etc/sysconfig/kuberdock/kuberdock.conf'


def upgrade(upd, with_testing, *args, **kwargs):
    try:
        from kubedock import amazon_settings
    except ImportError:
        upd.print_log('Not AWS, skipping')
        return

    aws_settings_names = ['AVAILABILITY_ZONE', 'AWS', 'AWS_ACCESS_KEY_ID',
                          'AWS_SECRET_ACCESS_KEY', 'REGION']

    config = ConfigParser()

    with open(settings.KUBERDOCK_SETTINGS_FILE, 'r+') as f:
        config.readfp(f)

        for setting in aws_settings_names:
            config.set('main', setting, getattr(amazon_settings, setting))
        config.set('main', 'AWS_EBS_DEFAULT_SIZE', 20)

        f.seek(0)
        config.write(f)

    run('rm {}'.format(os.path.join(settings.APP_ROOT, 'amazon_settings.py')))


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    pass


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass

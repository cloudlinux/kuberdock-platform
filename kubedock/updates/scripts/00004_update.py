import os

from alembic import command
from alembic.config import Config

base, _ = os.path.split(os.path.dirname(__file__))

location = os.path.join(base, 'kdmigrations')
conffile = os.path.join(location, 'alembic.ini')

acfg=Config(conffile)
acfg.set_main_option('script_location',location)

from kubedock.api import create_app

def upgrade(upd, with_testing, *args, **kwargs):
    print 'upgrade routine has been called'
    app = create_app()
    with app.app_context():
        command.upgrade(acfg, '144bf08f16b')

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    print 'downgrade routine has been called'
    app = create_app()
    with app.app_context():
        command.downgrade(acfg,'base')

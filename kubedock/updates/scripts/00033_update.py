from kubedock.core import db
from kubedock.predefined_apps.models import PredefinedApp
from kubedock.updates import helpers


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading db...')
    helpers.upgrade_db(revision='312700b6c892')

    for papp in PredefinedApp.query:
        papp.name = 'Predefined Application {0}'.format(papp.id)

    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Downgrading db...')
    helpers.downgrade_db(revision='299957c24510')

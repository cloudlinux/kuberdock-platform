from sqlalchemy import Table

from kubedock.core import db


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Drop table "node_missed_actions" if exists')
    table = Table('node_missed_actions', db.metadata)
    table.drop(bind=db.engine, checkfirst=True)
    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    try:
        from kubedock.nodes.models import NodeMissedAction
    except ImportError:
        upd.print_log('Cannot find NodeMissedAction model')
    else:
        upd.print_log('Create table for NodeMissedAction model if not exists')
        NodeMissedAction.__table__.create(bind=db.engine, checkfirst=True)
        db.session.commit()

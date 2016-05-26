from kubedock.core import db
from kubedock.notifications.models import Notification


def add_notifications():
    m1 = Notification(type='warning',
                        message='LICENSE_EXPIRED',
                        description='Your license has been expired.')
    m2 = Notification(type='warning',
                        message='NO_LICENSE',
                        description='License not found.')
    m3 = Notification(type='info',
                        message='CLN_NOTIFICATION',
                        description='')
    db.session.add_all([m1, m2, m3])

    db.session.commit()

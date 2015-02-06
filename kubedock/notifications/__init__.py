from .models import NotificationTemplate
from .events import (
    USER_CREATED, USER_CHANGED, USER_PWD_CHANGED, USER_PERM_CHANGED,
    USER_LOGGEDIN, POD_CONTAINER_CREATED, POD_CONTAINER_FAILED,
    POD_LIMITS_REACHED)


def send_notification(event, **kwargs):
    """
    :param event: Event Id
    :param kwargs: Objects of message context
    :return: None

    >>> from kubedock.notifications import send_notification, USER_CREATED
    >>> send_notification(USER_CREATED, user=user_object)
    """
    NotificationTemplate.send_notification(event, **kwargs)
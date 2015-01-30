import json
from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..notifications.models import NotificationTemplate
from ..notifications.events import NotificationEvent


notifications = Blueprint('notifications', __name__)


@notifications.route('/notifications/')
@notifications.route('/notifications/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    templates = NotificationTemplate.all()
    exist_events = [t.event for t in templates]
    context = dict(
        events=NotificationEvent.get_events(exclude=exist_events),
        events_keys=json.dumps(NotificationEvent.get_events_keys()),
        templates_collection=json.dumps([t.to_dict() for t in templates])
    )
    print context
    return render_template('notifications/index.html', **context)
import json
from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..api import settings as api_settings


settings = Blueprint('settings', __name__)


@settings.route('/settings/')
@settings.route('/settings/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    roles, permissions = api_settings.get_permissions()
    events_keys, notifications, events = api_settings.get_notifications()
    context = {'permissions': json.dumps(permissions),
               'roles': json.dumps(roles),
               'notifications': json.dumps(notifications),
               'events_keys': json.dumps(events_keys),
               'events': events}
    return render_template('settings/index.html', **context)


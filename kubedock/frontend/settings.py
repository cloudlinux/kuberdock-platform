import json
from flask import Blueprint, render_template
from flask.ext.login import login_required, current_user

from ..api import settings as api_settings
from ..settings import TEST


settings = Blueprint('settings', __name__, url_prefix='/settings')


@settings.route('/')
@settings.route('/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    roles, permissions = api_settings.get_permissions()
    events_keys, notifications, events = api_settings.get_notifications()
    context = {'permissions': json.dumps(permissions),
               'roles': json.dumps(roles),
               'this_user': json.dumps(current_user.to_dict(for_profile=True)),
               'notifications': json.dumps(notifications),
               'events_keys': json.dumps(events_keys),
               'events': events}
    return render_template('settings/index.html', **context)

@settings.route('/test', methods=['GET'])
def run_tests():
    if TEST:
        return render_template('t/settings_index.html')
    return "not found", 404
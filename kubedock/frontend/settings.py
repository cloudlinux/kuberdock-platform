from flask import Blueprint, render_template
from flask.ext.login import login_required

from ..api import settings as api_settings


settings = Blueprint('settings', __name__)


@settings.route('/settings/')
@settings.route('/settings/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    context = {}
    return render_template('settings/index.html', **context)


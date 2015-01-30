from flask import Blueprint, render_template

from ..static_pages.models import Menu


static_pages = Blueprint('menus', __name__)


@static_pages.route('/admin/static_pages/')
@static_pages.route('/admin/static_pages/<path:p>/', endpoint='other')
def index(**kwargs):
    """Returns the index page."""
    context = dict(regions=Menu.REGIONS, MENU=Menu.get_active())
    return render_template('static_pages/index.html', **context)

from flask import g, Blueprint, render_template
from flask.ext.login import login_required

from ..rbac import get_user_role
from ..users.models import Role
from ..static_pages.models import Menu, Page


static_pages = Blueprint('menus', __name__)


@static_pages.route('/admin/static_pages/')
@static_pages.route('/admin/static_pages/<path:p>/', endpoint='other')
@login_required
def index(**kwargs):
    """Returns the index page."""
    context = dict(
        regions=Menu.REGIONS,
        roles=Role.all(),
    )
    return render_template('static_pages/index.html', **context)


@static_pages.route('/page/<path:p>/', endpoint='other_page')
@login_required
def page(p):
    page = Page.filter_by(slug=p).first()
    if page is None:
        return 'Page "{0}" not found'.format(p), 404
    if not page.has_access(get_user_role()):
        return 'forbidden', 403
    return render_template('static_pages/page.html', page=page)

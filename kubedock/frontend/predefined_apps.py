import json
from flask import Blueprint, render_template, redirect, url_for
from flask.ext.login import current_user, login_required

#from ..predefined_apps import PredefinedApp


predefined_apps = Blueprint('predefined_apps', __name__, url_prefix='/predefined-apps')


@predefined_apps.route('/')
@login_required
def index():
    return render_template('predefined_apps/index.html')
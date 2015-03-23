from flask import Blueprint, request, jsonify

from . import APIError
from ..core import db, check_permission
from ..utils import login_required_or_basic


settings = Blueprint('settings', __name__, url_prefix='/settings')
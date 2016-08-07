from click import *
from core import *
from decorators import *


def abort():
    get_current_context().abort()

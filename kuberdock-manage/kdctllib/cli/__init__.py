import context
from kdclick import access
import settings


def initialize(current_role, settings):
    """Initialize cli with user role and application settings.

    Attention: Call this method before any other imports from module `cli`.
    """

    access.CURRENT_ROLE = current_role
    context.settings = settings

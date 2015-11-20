from .. import factory
from .. import sessions


def create_app(settings_override=None):
    app = factory.create_app(__name__, __path__, settings_override)
    app.session_interface = sessions.FakeSessionInterface()
    return app

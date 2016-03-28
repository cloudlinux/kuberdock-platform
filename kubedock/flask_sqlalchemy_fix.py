"""Bugfix for flask-sqlalchemy (sessions without sessionmaker).

Can be removed as soon as
https://github.com/mitsuhiko/flask-sqlalchemy/pull/148
is merged.
"""

from flask.ext.sqlalchemy import (
    orm, SessionBase, SQLAlchemy as SQLAlchemyWithBug,
    SignallingSession as SignallingSessionWithBug)


class SignallingSession(SignallingSessionWithBug):
    _db = None
    _options = {}

    def __init__(self, db=None, bind=None, **options):
        if db is None:
            db = self._db
        #: The application that this session belongs to.
        self.app = db.get_app()
        self._model_changes = {}
        options.update(self._options)
        options.setdefault('autocommit', False)
        options.setdefault('autoflush', False)
        options.setdefault('binds', db.get_binds(self.app))
        #: A flag that controls whether this session should keep track of
        #: model modifications.  The default value for this attribute
        #: is set from the ``SQLALCHEMY_TRACK_MODIFICATIONS`` config
        #: key.
        self.emit_modification_signals = \
            self.app.config['SQLALCHEMY_TRACK_MODIFICATIONS']
        bind = options.pop('bind', None) or db.engine
        SessionBase.__init__(self, bind=bind, **options)


class SQLAlchemy(SQLAlchemyWithBug):
    def create_scoped_session(self, options=None):
        if options is None:
            options = {}
        session_class = self.create_session_class(options)

        return orm.scoped_session(orm.sessionmaker(class_=session_class),
                                  scopefunc=options.pop('scopefunc', None))

    def create_session_class(self, options):
        return type("SignallingSession", (SignallingSession, ),
                    {'_db': self, '_options': options})

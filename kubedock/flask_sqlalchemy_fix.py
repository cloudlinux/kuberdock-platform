"""Bugfix for flask-sqlalchemy (sessions without sessionmaker).

Can be removed as soon as
https://github.com/mitsuhiko/flask-sqlalchemy/pull/148
is merged.
"""

from flask.ext.sqlalchemy import (
    orm,
    SQLAlchemy as SQLAlchemyWithBug,
    SignallingSession,
)


class SQLAlchemy(SQLAlchemyWithBug):
    def create_scoped_session(self, options=None):
        if options is None:
            options = {}
        scopefunc = options.pop('scopefunc', None)
        options['db'] = self
        return orm.scoped_session(
            orm.sessionmaker(class_=SignallingSession, **options),
            scopefunc=scopefunc)

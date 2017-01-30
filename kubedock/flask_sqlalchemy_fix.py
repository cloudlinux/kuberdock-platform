
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

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


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

import pytest
import sqlalchemy

from kubedock import testutils
from kubedock.core import db as _db
from kubedock.testutils import fixtures
from kubedock.testutils.testcases import DBTestCase


@pytest.fixture(scope='session')
def app():
    app_ = testutils.create_app(DBTestCase)
    ctx = app_.app_context()
    ctx.push()

    try:
        yield app_
    finally:
        ctx.pop()


@pytest.fixture(scope='session')
def db(app):
    """Session-wide test database."""
    meta = sqlalchemy.MetaData(bind=_db.engine)
    meta.reflect()
    for tbl in reversed(meta.sorted_tables):
        _db.engine.execute(tbl.delete())
    meta.drop_all()
    _db.reflect()
    _db.app = app
    _db.create_all()
    fixtures.initial_fixtures()

    try:
        yield _db
    finally:
        _db.drop_all()


@pytest.fixture(scope='function')
def session(db):
    """Creates a new database session for a test."""
    connection = db.engine.connect()
    transaction = connection.begin()

    options = dict(bind=connection, autoflush=False, autocommit=False)
    session_ = db.create_scoped_session(options=options)

    db.session = session_

    try:
        yield session_
    finally:
        transaction.rollback()
        connection.close()
        session_.remove()


@pytest.fixture(autouse=True)
def patch_license(mocker):
    mocker.patch('kubedock.kapi.licensing.is_valid', return_value=True)

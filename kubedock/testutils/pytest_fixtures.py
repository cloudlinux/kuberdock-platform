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

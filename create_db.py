from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Base, User, Container


engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
session = Session()

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


u1 = User('max', 'max@example.com', 'Max Doe', 'superpass1')
u2 = User('john', 'john@example.com', 'John Doe', 'superpass2')
u3 = User('alex', 'alex@example.com', 'Alex Doe', 'qwerty')

session.add_all([u1, u2, u3])
session.commit()

c1 = Container(
    name='mongodb test', docker_id='mongo', docker_tag='latest',
    desc='Database server', deployment_type='0', copies='1',
    size='XL', crash_recovery='1', auto_destroy='0', deployment_strategy='0',
    user_id='1')

c2 = Container(
    name='mongodb live', docker_id='mongo', docker_tag='latest',
    desc='Database server', deployment_type='0', copies='1',
    size='XL', crash_recovery='1', auto_destroy='0', deployment_strategy='0',
    user_id='2')

c3 = Container(
    name='ssh main', docker_id='ssh', docker_tag='latest',
    desc='SSH server', deployment_type='0', copies='1',
    size='XL', crash_recovery='1', auto_destroy='0', deployment_strategy='0',
    user_id='2')

c4 = Container(
    name='couchdb test', docker_id='couchdb', docker_tag='latest',
    desc='CouchDB server', deployment_type='0', copies='1',
    size='XL', crash_recovery='1', auto_destroy='0', deployment_strategy='0',
    user_id='1')

c5 = Container(
    name='redis live', docker_id='redis', docker_tag='latest',
    desc='Redis server', deployment_type='0', copies='1',
    size='L', crash_recovery='1', auto_destroy='0', deployment_strategy='0',
    user_id='1')

session.add_all([c1, c2, c3, c4, c5])
session.commit()

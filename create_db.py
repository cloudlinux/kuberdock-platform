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

c1 = Container('mongodb', 'mongo:latest', 'Database server', '0', '1',
               'XL', '1', '0', '0', '1')
c2 = Container('mongodb', 'mongo:latest', 'Database server', '0', '1',
               'XS', '1', '0', '0', '2')
c3 = Container('ssh', 'ssh:latest', 'SSH server', '0', '1',
               'XS', '1', '0', '0', '2')
c3 = Container('redis', 'redis:latest', 'Redis server', '0', '1',
               'XM', '1', '0', '0', '2')
c4 = Container('couchdb', 'couchdb:latest', 'CouchDB server', '0', '1',
               'XM', '1', '0', '0', '1')

session.add_all([c1, c2, c3, c4])
session.commit()

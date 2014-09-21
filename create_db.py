from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL
from models import Base, User, Container


engine = create_engine(DATABASE_URL)
Session = sessionmaker(engine)
session = Session()

Base.metadata.drop_all(engine)
Base.metadata.create_all(engine)


admin = User('admin', 'admin@example.com', 'John Doe', 'superpass')
guest = User('guest', 'guest@example.com', 'Another Name', 'qwerty')

session.add(admin)
session.add(guest)
session.commit()

# c1 = Container('mongodb', 'Database server')
# c2 = Container('ssh', 'SSH server')
# c3 = Container('redis', 'Redis server')
# c3 = Container('couchdb', 'CouchDB server')
# session.add(c1)
# session.add(c2)
# session.add(c3)
# session.commit()

from models import Base, User, Container
from app import engine, session

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

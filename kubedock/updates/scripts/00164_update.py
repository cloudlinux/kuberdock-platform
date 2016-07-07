from random import sample
from string import lowercase, uppercase, digits

from kubedock.settings import KUBERDOCK_SETTINGS_FILE


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Generating secret key...')
    random_string = ''.join(sample(lowercase + uppercase + digits, 32))
    with open(KUBERDOCK_SETTINGS_FILE, 'a') as c:
        c.write("SECRET_KEY={0}\n".format(random_string))


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('No downgrade provided')
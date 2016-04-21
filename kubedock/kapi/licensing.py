import json
import uuid
import datetime
import dateutil.parser

from kubedock.kapi.notifications import attach_admin, detach_admin

import pytz

from ..utils import APIError
from ..validation import V


LICENSE_PATH = '/var/opt/kuberdock/.license'
HELPDESK_LINK = 'https://helpdesk.cloudlinux.com'


PUBLIC_KEY =\
"""MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAsULvbFc8v7+HiQo5o4yn
qgg0nAikdVmsS7QUf5zsFIjkfYeHCUEDuLO3mzXrXzLuXjm1LHQPGtlxNhaB7PDz
azH2Uzw5mYNawKz8lJa93Iw3gz9BtIhGHdKWtEPPMXxGo5icQYZOKsLIiO3pQh3v
ihcQywHu8iNjE7fJ3+8wPpv7qfeNS2FG3BBYsFxOVARKKTWWLIQ2CF9KaJDSUoGs
97pQ3UIivOw7YrZDvtZyPJcBQg+GpVlyKyzU8WmBPMHoBFWHDaRQXngz4b5pQaYD
yZNYIHK3nqflSLxU1Xlifd2TTO+2bel6TwtdKOl8BE8Ol/od5gw/2vmKqfNtCcXg
OFwhe6xnKTBiBvbl7VlW/zYhThMdcapNaKx/TAIb+Jmi9m4sY0vz+vMObjWpBinD
FWaCMwORE4Nhe2QbCgpkeS+frcDJf8v4Y1AouAFtj2pckZmtX8c7LYC5AzF2X/np
jRW8L+Z72hq239pjpuyp/9gdLUpp3zoicjCiMO7YlqumMj5Vvu9thqc3Y2FW4K18
sXFeu/R1hNPgQs1nPArvBreRchJMtI4P+FesS16yxRl6pMO+ewMoLuGHYhT6x+PW
gxE7c6xbS5KegtqUImADWdk6zw/QYnCPwef59b24U2w11FD549epea7XUIHavUwC
aZUeyc+SFioGW+5zbzhU3DMCAwEAAQ=="""


def get_auth_key():
    data = _load_license()
    if data is None:
        raise APIError('Invalid license data')
    return data.get('auth_key', '')


def generate_auth_key():
    authkey = uuid.uuid4().hex
    data = {'auth_key': authkey}
    _save_license(data)
    return authkey


def get_license_info():
    data = _load_license()
    if data is not None:
        _check_license_sign(data)
    else:
        generate_auth_key()
        data = _load_license()
    return data


def update_license_data(license_data):
    data = _load_license()
    if data is None:
        return
    data['updated'] = datetime.datetime.now().replace(
        tzinfo=pytz.UTC
    ).isoformat()
    data['data'] = license_data
    _check_license(data)
    _check_notifications(data)
    _save_license(data)


def _check_license(data):
    if is_status_ok(data):
        detach_admin('NO_LICENSE')
    else:
        attach_admin('NO_LICENSE', ' Please visit ' + HELPDESK_LINK)


def _check_notifications(data):
    detach_admin('CLN_NOTIFICATION')
    notification = data.get('data', {}).get('license', {}).get('notification')
    if notification:
        message = notification.get('message', 'default message')
        url = notification.get('url', HELPDESK_LINK)
        target = '{0} {1}'.format(message, url)
        attach_admin('CLN_NOTIFICATION', target)


def update_installation_id(installation_id):
    V()._api_validation({'installation_id': installation_id},
                        {'installation_id': {'type': 'string', 'empty': False}})
    data = _load_license()
    if data is None:
        return
    data['installationID'] = installation_id
    _save_license(data)


def is_status_ok(lic):
    if lic.get('data', {}).get('license', {}).get('status', '') == 'ok':
        return True
    return False


def is_timestamp_ok(lic):
    updated = lic.get('updated', False)
    if not updated:
        return False
    updated = dateutil.parser.parse(updated)
    now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
    if (now - updated).days > 3:
        return False
    return True


def is_valid():
    lic = get_license_info()
    if is_status_ok(lic) or is_timestamp_ok(lic):
        return True
    return False


def _load_license():
    try:
        with open(LICENSE_PATH, 'r') as fin:
            return json.load(fin)
    except:
        return None


def _save_license(data):
    with open(LICENSE_PATH, 'w') as fout:
        json.dump(data, fout)


def _check_license_sign(data):
    pass

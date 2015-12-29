import json
import uuid
import datetime
import dateutil.parser

from kubedock.kapi.notifications import attach_admin, detach_admin

import pytz

from ..utils import APIError

LICENSE_PATH = '/var/opt/kuberdock/.license'


PUBLIC_KEY =\
"""MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEAzB4O9iGYFP+PhtDhnxwb
QmF8LGRlqY8Hxw3e/3vjlpm1VlYzHEmpanIK8GA8vX2sKzkL5p4wV23AitLzFETT
HlrIqFHUKxR2gnC4K5LromgPepxRj5foUu5qb+jzpD+YLcGbzKNdFIeRwiP3L1Uq
kAz7HN5iJvAXX0hN2C83YvEJWsbHn3HwcZXB0T5kkhAn1zdRXvdlaY3TD4058f5I
FY0PS2gkislqf1y8li5yAhWTwlSu/jXCoYkZfZQ1YirUfmV9r78+YprJgo6LQnXo
N16nW0Lz6mOJt67q0X6nzqCuTTbLBdr7ruhEr/+/ufK1HAGZ7wqqi999svSDfGrm
lMTnZTJtsgOm7gWkLdAddKE3hzhMaS7siRJfR25EO1U4x0D4TqLtP6SK2hMxkVXa
orB8QAnZu28xjiubfmP6650g+l8gFVy8M5Dyj20eJque6lNxymTwedlpWz2AZAJx
LYI+aE4N5YAIrL/7gbWQUzJO3yDSRO1EB/SH61/KNwqiNXJhvPIb22UlvFP40eRC
Zz4fBYSOYCH2/AhoFGuPRtPcqiWl2Ph750jWfmZKF3pzCqzJ0pj3ndydqbFurQh7
csoqSsSYRxagHPjoFdJhZrIzwf2zui+nWtG6OhdGrqC9MMp2THWuT9hLKqqVloMw
NulHZIiWZzQOKsgxeTEkTzUCAwEAAQ=="""


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
    if is_status_ok(data):
        detach_admin('NO_LICENSE')
    else:
        attach_admin('NO_LICENSE', ' Please visit http://kuberdock.com')
    _save_license(data)


def update_installation_id(installation_id):
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
    if (now - updated).seconds > 259200: # 3 days
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

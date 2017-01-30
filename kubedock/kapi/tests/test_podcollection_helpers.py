
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

import mock

from kubedock.kapi import podcollection
from kubedock.models import BaseDomain, PodDomain
from kubedock.testutils.pytest_fixtures import *
from kubedock.validation import ValidationError


public_access_parameters_valid = 'is_aws, conf_in, exp_conf_out', [
    (False,
     {},
     {'public_access_type': 'public_ip', 'public_ip': None}),
    (True,
     {},
     {'public_access_type': 'public_aws', 'public_aws': None}),
    (True,
     {'public_access_type': 'public_aws'},
     {'public_access_type': 'public_aws', 'public_aws': None}),
    (True,
     {'public_access_type': 'public_aws', 'public_aws': 'my.aws.com'},
     {'public_access_type': 'public_aws', 'public_aws': 'my.aws.com'}),
    (False,
     {'public_ip': None},
     {'public_access_type': 'public_ip', 'public_ip': None}),
    (False,
     {'public_ip': '1.2.3.4'},
     {'public_access_type': 'public_ip', 'public_ip': '1.2.3.4'}),
    (False,
     {'public_access_type': 'public_ip'},
     {'public_access_type': 'public_ip', 'public_ip': None}),
    (False,
     {'public_access_type': 'public_ip', 'public_ip': None},
     {'public_access_type': 'public_ip', 'public_ip': None}),
    (False,
     {'public_access_type': 'public_ip', 'public_ip': '1.2.3.4'},
     {'public_access_type': 'public_ip', 'public_ip': '1.2.3.4'}),
    (False,
     {'domain': 'a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com', 'domain': None}),
    (False,
     {'public_access_type': 'domain', 'domain': 'a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com', 'domain': None}),
    (False,
     {'base_domain': 'a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com', 'domain': None}),
    (False,
     {'public_access_type': 'domain', 'base_domain': 'a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com', 'domain': None}),
    (False,
     {'base_domain': 'a.com', 'domain': 'b.a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com',
      'domain': 'b.a.com'}),

    # check base_domain extracting
    (False,
     {'domain': 'b.a.com'},
     {'public_access_type': 'domain', 'base_domain': 'a.com',
      'domain': 'b.a.com'}),
]

public_access_parameters_inconsistent = 'is_aws, conf_in', [
    # unknown public access type
    (False, {'public_access_type': 'bla-bla'}),

    # no domain specified, failed
    (False, {'public_access_type': 'domain'}),

    # base domain not found for specified domain
    (False, {'domain': 'foo.bar.com'}),

    # pod domain is not sub-domain of base domain
    (False, {'base_domain': 'a.com', 'domain': 'bla-bla'}),
    (False, {'base_domain': 'a.com', 'domain': 'b.b.com'}),

    # specified both domain and public ip
    (False, {'public_ip': '1.2.3.4', 'domain': 'a.com'}),
    (False, {'public_ip': '1.2.3.4', 'base_domain': 'a.com'}),

    # conflict between specified public access type and data
    (False, {'public_access_type': 'public_ip', 'domain': 'a.com'}),
    (False, {'public_access_type': 'public_ip', 'base_domain': 'a.com'}),
    (False, {'public_access_type': 'domain', 'public_ip': '1.2.3.4'}),
    (False, {'public_access_type': 'public_ip', 'public_ip': '1.2.3.4',
             'domain': 'a.com'}),
    (False, {'public_access_type': 'public_ip', 'public_ip': '1.2.3.4',
             'base_domain': 'a.com'}),
    (False, {'public_access_type': 'domain', 'public_ip': '1.2.3.4',
             'domain': 'a.com'}),
    (False, {'public_access_type': 'domain', 'public_ip': '1.2.3.4',
             'base_domain': 'a.com'}),

    # aws
    (True, {'public_access_type': 'public_ip'}),
    (True, {'public_access_type': 'domain'}),
    (True, {'domain': 'a.com'}),
    (True, {'base_domain': 'a.com'}),
    (True, {'public_ip': None}),
    (True, {'public_ip': '1.2.3.4'}),
]


@pytest.fixture()
def base_domain(session):
    rv = BaseDomain.create(name='a.com')
    session.add(rv)
    session.flush()
    return rv


@pytest.mark.usefixtures('base_domain')
@pytest.mark.parametrize(*public_access_parameters_valid)
def test_preprocess_public_access_valid(is_aws, conf_in, exp_conf_out, app):
    app.config['AWS'] = is_aws
    podcollection.PodCollection._preprocess_public_access(conf_in)
    assert conf_in == exp_conf_out
    # conf_in modified after _preprocess
    conditions = [
        bool(conf_in.get('base_domain')) and 'domain' in conf_in,
        'public_aws' in conf_in,
        'public_ip' in conf_in
    ]
    assert sum(conditions) == 1


@pytest.mark.usefixtures('base_domain')
@pytest.mark.parametrize(*public_access_parameters_inconsistent)
def test_preprocess_public_access_inconsistent(is_aws, conf_in, app):
    app.config['AWS'] = is_aws
    with pytest.raises(ValidationError):
        podcollection.PodCollection._preprocess_public_access(conf_in)

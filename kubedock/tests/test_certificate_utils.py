
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

import os.path
from itertools import permutations

import pytest

from ..certificate_utils import (check_cert_is_valid_for_domain,
                                 check_cert_matches_private_key,
                                 extract_domains_from_cert_extensions,
                                 load_certificate_from_file)
from ..exceptions import CertificatDoesNotMatchDomain


@pytest.fixture
def certs_path():
    return 'kubedock/testutils/certificates/'


certificates = [
    {
        'cert': 'subalt_www.test_domain.com.crt',
        'key': 'subalt_www.test_domain.com.key',
        'CN': 'test_domain.com',
        'alt_names': ['www.test_domain.com', 'www2.test_domain.com'],
    },
    {
        'cert': 'test_domain.com.crt',
        'key': 'test_domain.com.key',
        'CN': 'test_domain.com',
        'alt_names': [],
    },
    {
        'cert': 'wildcard.tetst_domain.com.crt',
        'key': 'wildcard.tetst_domain.com.key',
        'CN': '*.test_domain.com',
        'alt_names': [],
    }
]


@pytest.mark.parametrize('cert', certificates)
def test_extract_domains_from_cert_extensions_returns_correct_set_of_domains(
        cert, certs_path):

    u = load_certificate_from_file(certs_path + cert['cert'])

    extensions = (
        u.get_extension(i) for i in range(u.get_extension_count()))

    domains = extract_domains_from_cert_extensions(extensions)
    assert set(domains) == set(cert['alt_names'])


@pytest.mark.parametrize('cert', certificates)
def test_check_cert_is_valid_for_domain_succeeds_if_domain_is_a_common_name(
        cert, certs_path):

    with open(os.path.join(certs_path, cert['cert'])) as f:
        check_cert_is_valid_for_domain(cert['CN'], f.read())


@pytest.mark.parametrize('cert', certificates)
def test_check_cert_is_valid_for_domain_pass_if_domain_is_in_subject_alt_name(
        cert, certs_path):

    with open(os.path.join(certs_path,  cert['cert'])) as f:
        pub = f.read()
        for domain in cert['alt_names']:
            check_cert_is_valid_for_domain(domain, pub)


@pytest.mark.parametrize('cert', certificates)
def test_check_cert_is_valid_for_domain_fails_if_domain_does_not_match(
        cert, certs_path):

    with open(os.path.join(certs_path,  cert['cert'])) as f:
        pub = f.read()
        with pytest.raises(CertificatDoesNotMatchDomain):
            check_cert_is_valid_for_domain('wrong_domain.com', pub)


@pytest.mark.parametrize('cert', certificates)
def test_check_cert_matches_private_key_passes_on_matching_key_pair(
        cert, certs_path):

    cert_path = os.path.join(certs_path, cert['cert'])
    key_path = os.path.join(certs_path, cert['key'])
    with open(cert_path) as c, open(key_path) as k:
        assert check_cert_matches_private_key(c.read(), k.read())


@pytest.mark.parametrize('cert_a, cert_b', permutations(certificates, 2))
def test_check_cert_matches_private_key_fails_if_cert_key_does_not_match(
        cert_a, cert_b, certs_path):

    cert_path = os.path.join(certs_path, cert_a['cert'])
    key_path = os.path.join(certs_path, cert_b['key'])
    with open(cert_path) as c, open(key_path) as k:
        assert not check_cert_matches_private_key(c.read(), k.read())

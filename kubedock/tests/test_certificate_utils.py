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

import re
from itertools import chain

from OpenSSL import SSL, crypto
from pyasn1.codec.der import decoder as der_decoder

from . import exceptions
from .pyasn_structures import SubjectAltName


# Backported from python 3 SSL library
class CertificateError(ValueError):
    pass


def _dnsname_match(dn, hostname, max_wildcards=1):
    """Matching according to RFC 6125, section 6.4.3

    http://tools.ietf.org/html/rfc6125#section-6.4.3
    """
    pats = []
    if not dn:
        return False

    # Ported from python3-syntax:
    # leftmost, *remainder = dn.split(r'.')
    parts = dn.split(r'.')
    leftmost = parts[0]
    remainder = parts[1:]

    wildcards = leftmost.count('*')
    if wildcards > max_wildcards:
        # Issue #17980: avoid denials of service by refusing more
        # than one wildcard per fragment.  A survey of established
        # policy among SSL implementations showed it to be a
        # reasonable choice.
        raise CertificateError(
            "too many wildcards in certificate DNS name: " + repr(dn))

    # speed up common case w/o wildcards
    if not wildcards:
        return dn.lower() == hostname.lower()

    # RFC 6125, section 6.4.3, subitem 1.
    # The client SHOULD NOT attempt to match a presented identifier in which
    # the wildcard character comprises a label other than the left-most label.
    if leftmost == '*':
        # When '*' is a fragment by itself, it matches a non-empty dotless
        # fragment.
        pats.append('[^.]+')
    elif leftmost.startswith('xn--') or hostname.startswith('xn--'):
        # RFC 6125, section 6.4.3, subitem 3.
        # The client SHOULD NOT attempt to match a presented identifier
        # where the wildcard character is embedded within an A-label or
        # U-label of an internationalized domain name.
        pats.append(re.escape(leftmost))
    else:
        # Otherwise, '*' matches any dotless string, e.g. www*
        pats.append(re.escape(leftmost).replace(r'\*', '[^.]*'))

    # add the remaining fragments, ignore any wildcards
    for frag in remainder:
        pats.append(re.escape(frag))

    pat = re.compile(r'\A' + r'\.'.join(pats) + r'\Z', re.IGNORECASE)
    return pat.match(hostname)

#######################################################################


def load_certificate_from_file(path):
    with open(path) as f:
        return crypto.load_certificate(crypto.FILETYPE_PEM, f.read())


def extract_domains_from_cert_extensions(extensions):
    general_names = SubjectAltName()
    extensions_data = (
        der_decoder.decode(e.get_data(), asn1Spec=general_names)
        for e in extensions if e.get_short_name() == 'subjectAltName'
    )

    return [
        str(name.getComponentByPosition(i).getComponent())
        for data in extensions_data
        for name in data
        for i, _ in enumerate(name) if isinstance(name, SubjectAltName)
    ]


def check_cert_is_valid_for_domain(domain, cert):
    c = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
    subject = c.get_subject()

    extensions = (c.get_extension(i) for i in range(c.get_extension_count()))
    subject_alt_names = extract_domains_from_cert_extensions(extensions)
    domain_list = {d for d in chain(subject_alt_names)}
    domain_list.add(subject.commonName)

    if not any(_dnsname_match(d, domain) for d in domain_list):
        raise exceptions.CertificatDoesNotMatchDomain(domain, domain_list)


def check_cert_matches_private_key(cert, private_key):
    priv_key = crypto.load_privatekey(crypto.FILETYPE_PEM, private_key)
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, cert)

    context = SSL.Context(SSL.TLSv1_METHOD)
    context.use_privatekey(priv_key)
    context.use_certificate(cert)
    try:
        context.check_privatekey()
        return True
    except SSL.Error:
        return False

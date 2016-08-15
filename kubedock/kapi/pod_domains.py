import string

from ..core import db
from ..domains.models import PodDomain, BaseDomain
from ..utils import domainize, randstr
from ..exceptions import NotFound, InternalAPIError


def set_pod_domain(pod, domain_id):
    """
    Generate new or return existing domain name for IP sharing
    New domain name will be generated as
    <domainized username>-<domainized pod name>
    If that name already exists, then will be appended some random suffix to
    it.

    :param pod: Pod object
    :type pod: kubedock.pods.models.Pod
    :param domain_id: Parent BaseDomain model identifier
    :type domain: integer
    :return: instance of PodDomain model
    :rtype: kubedock.domains.models.PodDomain
    """

    pod_domain = PodDomain.query.filter_by(
        domain_id=domain_id, pod_id=pod.id).first()
    if pod_domain is not None:
        return pod_domain

    pod_name = domainize(pod.name)
    if not pod_name:
        pod_name = randstr(symbols=string.lowercase + string.digits, length=8)
    user = domainize(pod.owner.username)
    pod_domain_name = '{0}-{1}'.format(user, pod_name)
    pod_domain_name = _get_unique_domain_name(pod_domain_name, domain_id)
    if pod_domain_name is None:
        raise InternalAPIError('Failed to get unique pod domain name')
    pod_domain = PodDomain(name=pod_domain_name, domain_id=domain_id,
                           pod_id=pod.id)
    db.session.add(pod_domain)
    return pod_domain


def _get_unique_domain_name(basename, domain_id):
    """Returns unique domain name for given basename.
    If basename does not exists in DB with specified domain_id, then it will
    be returned as is.
    Otherwise will be returned basename with random suffix
    """
    pod_domain = PodDomain.query.filter_by(name=basename,
                                           domain_id=domain_id).first()
    if pod_domain is None:
        return basename

    res = None
    # try to get unique random domain name. If it fails for tries limit,
    # then something is going wrong, return None and it will be better to fail
    # in calling code
    tries_limit = 100
    random_suffix_length = 6
    for _ in xrange(tries_limit):
        suffix = randstr(
            symbols=string.lowercase + string.digits,
            length=random_suffix_length)
        new_name = '{0}{1}'.format(basename, suffix)
        pod_domain = PodDomain.query.filter_by(
            name=new_name, domain_id=domain_id).first()
        if pod_domain is None:
            res = new_name
            break
    return res


def check_domain(domain_name):
    """
    Make sure that domain name exists

    :param domain_name: Parent BaseDomain Name
    :type domain_name: str
    :return: BaseDomain object specified by domain_name
    :rtype: kubedock.domains.models.BaseDomain
    :raises NotFound: If BaseDomain with specified domain_name can't be found
    """

    domain = BaseDomain.query.filter_by(name=domain_name).first()
    if domain is None:
        raise NotFound("Can't find domain ({0})".format(domain_name))
    return domain

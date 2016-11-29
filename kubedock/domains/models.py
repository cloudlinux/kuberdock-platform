"""Models for dns management susbsytem with IP sharing via ingress controller.
"""
from sqlalchemy.schema import UniqueConstraint
from sqlalchemy.dialects import postgresql

from ..core import db
from ..constants import DOMAINNAME_LENGTH
from ..pods.models import Pod
from ..models_mixin import BaseModelMixin


class BaseDomain(BaseModelMixin, db.Model):
    """Model for domain names, which should be used as a base domains
    for pod domains (pod domain is subdomain of this BaseDomain)
    """
    __tablename__ = 'base_domains'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(DOMAINNAME_LENGTH), nullable=False, unique=True)

    # Wildcard certificate which is used in shared IP case if present
    certificate_cert = db.Column(db.String(8192), nullable=True)
    certificate_key = db.Column(db.String(8192), nullable=True)

    @property
    def certificate(self):
        if self.certificate_cert and self.certificate_key:
            return {'cert': self.certificate_cert, 'key': self.certificate_key}

    @certificate.setter
    def certificate(self, v):
        self.certificate_cert, self.certificate_key = v['cert'], v['key']

    def __repr__(self):
        return '{0}(id={1}, name="{2}")'.format(
            self.__class__.__name__,
            self.id,
            self.name,
        )

    def __str__(self):
        return self.name


class PodDomain(db.Model):
    """Subdomains for BaseDomain which used for pods.
    PodDomain.name + '.' + BaseDomain.name = full domain name of a pod.
    """
    __tablename__ = 'pod_domains'

    id = db.Column(db.Integer, primary_key=True)
    # link to base domain where pod's subdomain is.
    domain_id = db.Column(
        db.Integer, db.ForeignKey(BaseDomain.id), nullable=False)
    # Pod's subdomain name
    name = db.Column(db.String(DOMAINNAME_LENGTH), nullable=False)
    # Link to a pod owns this domain
    pod_id = db.Column(postgresql.UUID, db.ForeignKey('pods.id'))
    # Linked BaseDomain record
    base_domain = db.relationship(BaseDomain,
                                  backref=db.backref('pod_domains'))
    # Linked Pod
    pod = db.relationship(Pod, backref=db.backref('domains'))

    __table_args__ = (
        UniqueConstraint(domain_id, name),
        UniqueConstraint(domain_id, pod_id),
    )

    @staticmethod
    def find_by_full_domain(full_domain_name):
        """
        Find Pod Domain by string representation

        :param full_domain_name: Full Pod Domain Name
        :type full_domain_name: str
        :return: Pod Domain object or None if Pod Domain can't be found
        :rtype: PodDomain | None
        """

        name, domain_name = full_domain_name.split('.', 1)
        return PodDomain.query.filter(
            PodDomain.name == name,
            PodDomain.base_domain.has(BaseDomain.name == domain_name)
        ).first()

    def __repr__(self):
        return '{0}(id={1}, domain_id={2}, name="{3}", pod_id={4})'.format(
            self.__class__.__name__,
            self.id,
            self.domain_id,
            self.name,
            self.pod_id,
        )

    def __str__(self):
        return '{0}.{1}'.format(self.name, self.base_domain.name)

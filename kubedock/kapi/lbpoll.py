from kubedock.kapi.helpers import Services
from kubedock.kapi.podutils import raise_if_failure
from kubedock.settings import AWS

PUBLIC_SVC_TYPE = 'public'


def get_service_provider():
    if AWS:
        return LoadBalanceService()
    else:
        return ExternalIPsService()


class LoadBalanceService(Services):
    """Return Services that response for ingress public addresses"""

    def __init__(self):
        super(LoadBalanceService, self).__init__(PUBLIC_SVC_TYPE)

    def get_template(self, pod_id, ports):
        template = super(LoadBalanceService, self).get_template(pod_id, ports)

        template['spec']['type'] = 'LoadBalancer'
        return template

    @staticmethod
    def get_public_dns(service):
        if service['spec']['type'] == 'LoadBalancer':
            ingress = service['status']['loadBalancer'].get('ingress', [])
            if ingress and 'hostname' in ingress[0]:
                hostname = ingress[0]['hostname']
                return hostname

    def get_pods_public_dns(self, services):
        svc = {}
        for pod, s in services.iteritems():
            public_dns = self.get_public_dns(s)
            if public_dns:
                svc[pod] = public_dns
        return svc

    def get_dns_all(self):
        svc = self.get_all()
        return [self.get_public_dns(s) for s in svc]

    def get_dns_by_pods(self, pods):
        svc = self.get_by_pods(pods)
        return self.get_pods_public_dns(svc)

    def get_dns_by_user(self, user_id):
        svc = self.get_by_user(user_id)
        return self.get_pods_public_dns(svc)


class ExternalIPsService(Services):

    def __init__(self):
        super(ExternalIPsService, self).__init__(PUBLIC_SVC_TYPE)

    @staticmethod
    def get_publicIP(service):
        try:
            return service['spec']['externalIPs'][0]
        except (KeyError, IndexError):
            return None

    def set_publicIP(self, service, publicIP):
        if publicIP:
            service['spec']['externalIPs'] = [publicIP]
        return service

    def update_publicIP(self, service, publicIP=None):
        """Update publicIP in service
        :param service: service to update
        :param publicIP: new publicIP for service
        :return: updated service
        """
        name = service['metadata']['name']
        namespace = service['metadata']['namespace']
        data = {'spec': {'externalIPs': [publicIP]}}
        rv = self.patch(name, namespace, data)
        raise_if_failure(rv, "Couldn't patch service publicIP")
        return rv

    def get_pods_publicIP(self, services):
        svc = {}
        for pod, s in services.iteritems():
            publicIP = self.get_publicIP(s)
            if publicIP:
                svc[pod] = publicIP
        return svc

    def get_publicIP_all(self):
        svc = self.get_all()
        return [self.get_publicIP(s) for s  in svc]

    def get_publicIP_by_pods(self, pods):
        svc = self.get_by_pods(pods)
        return self.get_pods_publicIP(svc)

    def get_publicIP_by_user(self, user_id):
        svc = self.get_by_user(user_id)
        return self.get_pods_publicIP(svc)

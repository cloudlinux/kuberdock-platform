from kubedock.kapi.helpers import Services

PUBLIC_SVC_TYPE = 'public'


class LoadBalanceService(Services):
    """Return Services that response for ingress public addresses"""

    def __init__(self):
        return super(LoadBalanceService, self).__init__(PUBLIC_SVC_TYPE)

    def get_public_dns(self, service):
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

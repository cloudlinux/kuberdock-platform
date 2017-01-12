# KuberDock service pods names
# Pod name for ingress controller default backend
KUBERDOCK_BACKEND_POD_NAME = 'kuberdock-default-backend'
# Pod name for ingress controller
KUBERDOCK_INGRESS_POD_NAME = 'kuberdock-ingress-controller'
# ConfigMap resource name where the defaults for the nginx inside ingress
# controller are stored
KUBERDOCK_INGRESS_CONFIG_MAP_NAME = 'ingress-load-balancer-conf'
KUBERDOCK_INGRESS_CONFIG_MAP_NAMESPACE = 'default'
# Fields Length
DOMAINNAME_LENGTH = 255

AWS_UNKNOWN_ADDRESS = 'Unknown'

# If pod scheduling failed due to lack of resources/nodes on cluster we
# send messages to admin and user, but we don't want to sent it too often
# so we throttle them to once per this ttl:
POD_FAILED_SCHEDULING_THROTTLING_TTL = 1 * 60 * 60   # 1 hour


class REDIS_KEYS:
    # used by utils.throttle():
    THROTTLE_PREFIX = 'throttled_evt_'

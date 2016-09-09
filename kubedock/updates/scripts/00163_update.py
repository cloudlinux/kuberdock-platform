import os
from kubedock.updates import helpers
from fabric.api import run, put, lcd, local
from kubedock.settings import MASTER_IP

HOSTNAME = os.environ.get("HOSTNAME")
KUBERNETES_CERTS_DIR = '/etc/kubernetes/certs'

K8S_TLS_CERT = "{0}/{1}.crt".format(KUBERNETES_CERTS_DIR, HOSTNAME)
K8S_TLS_PRIVATE_KEY = "{0}/{1}.key".format(KUBERNETES_CERTS_DIR, HOSTNAME)
K8S_CA_CERT=KUBERNETES_CERTS_DIR + '/ca.crt'

def upgrade(upd, with_testing, *args, **kwargs):
    # upd.print_log("Generating key for service account")
    sans="IP:{0},IP:10.254.0.1,DNS:kubernetes,DNS:kubernetes.default,DNS:kubernetes.default.svc,DNS:$(hostname)".format(MASTER_IP)
    tempdir = local('mktemp -d', capture=True)
    with lcd(tempdir):
        local('curl -k -L -O --connect-timeout 20 --retry 6 --retry-delay 2 '
              'https://storage.googleapis.com/kubernetes-release/easy-rsa/'
              'easy-rsa.tar.gz')
        local('tar xzf easy-rsa.tar.gz')
    with lcd(os.path.join(tempdir, 'easy-rsa-master/easyrsa3')):
        local('./easyrsa init-pki')
        local('./easyrsa --batch "--req-cn={primary_cn}@$(date +%s)" '
                'build-ca nopass'.format(primary_cn=MASTER_IP))
        local('./easyrsa --subject-alt-name="{sans}" build-server-full '
                '"$(hostname)" nopass'.format(sans=sans))

        local('mkdir -p {certs_dir}'.format(certs_dir=KUBERNETES_CERTS_DIR))
        local('mv ./pki/ca.crt {certs_dir}/'
              .format(certs_dir=KUBERNETES_CERTS_DIR))
        local('mv ./pki/issued/* {certs_dir}/'
              .format(certs_dir=KUBERNETES_CERTS_DIR))
        local('mv ./pki/private/* {certs_dir}/'
              .format(certs_dir=KUBERNETES_CERTS_DIR))
        local('chown -R kube:kube {certs_dir}'
              .format(certs_dir=KUBERNETES_CERTS_DIR))
        local('chmod -R 0440 {certs_dir}/*'
              .format(certs_dir=KUBERNETES_CERTS_DIR))

    # upd.print_log("Updating apiserver config")
    helpers.update_local_config_file(
        "/etc/kubernetes/apiserver",
        {
            "KUBE_API_ARGS":
                {
                    "--tls-cert-file=": K8S_TLS_CERT,
                    "--tls-private-key-file=": K8S_TLS_PRIVATE_KEY,
                    "--client-ca-file=": K8S_CA_CERT,
                    "--service-account-key-file=": K8S_TLS_CERT,
                }
        }
    )
    # upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file(
        "/etc/kubernetes/controller-manager",
        {
            "KUBE_CONTROLLER_MANAGER_ARGS":
                {
                    "--service-account-private-key-file=": K8S_TLS_PRIVATE_KEY,
                    "--root-ca-file=": K8S_CA_CERT
                }
        }
    )
    helpers.local('systemctl restart kube-apiserver', capture=False)

def downgrade(upd, with_testing, exception, *args, **kwargs):
    # upd.print_log("Updating apiserver config")
    helpers.update_local_config_file(
        "/etc/kubernetes/apiserver",
        {
            "KUBE_API_ARGS":
                {
                    "--tls-cert-file=": None,
                    "--tls-private-key-file=": None,
                    "--client-ca-file=": None,
                    "--service-account-key-file": None,
                }
        }
    )
    # upd.print_log("Updating controller-manager config")
    helpers.update_local_config_file(
        "/etc/kubernetes/controller-manager",
        {
            "KUBE_CONTROLLER_MANAGER_ARGS":
                {
                    "--service_account_private_key_file=": None,
                    "--root-ca-file=": None
                }
        }
    )
    helpers.local('systemctl restart kube-apiserver', capture=False)

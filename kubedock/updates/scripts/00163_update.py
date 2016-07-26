import os
from kubedock.updates import helpers
from kubedock.settings import MASTER_IP

HOSTNAME = os.environ.get("HOSTNAME")
KUBERNETES_CERTS_DIR = '/etc/kubernetes/certs'

K8S_TLS_CERT = "{0}/{1}.crt".format(KUBERNETES_CERTS_DIR, HOSTNAME)
K8S_TLS_PRIVATE_KEY = "{0}/{1}.key".format(KUBERNETES_CERTS_DIR, HOSTNAME)
K8S_CA_CERT=KUBERNETES_CERTS_DIR + '/ca.crt'

def upgrade(upd, with_testing, *args, **kwargs):
    # upd.print_log("Generating key for service account")
    sans="IP:{0},DNS:kubernetes,DNS:kubernetes.default,DNS:kubernetes.default.svc,DNS:$(hostname)".format(MASTER_IP)
    helpers.local("""
cd `mktemp -d`
curl -L -O --connect-timeout 20 --retry 6 --retry-delay 2 https://storage.googleapis.com/kubernetes-release/easy-rsa/easy-rsa.tar.gz
tar xzf easy-rsa.tar.gz
cd easy-rsa-master/easyrsa3
./easyrsa init-pki
./easyrsa --batch "--req-cn={primary_cn}@$(date +%s)" build-ca nopass
./easyrsa --subject-alt-name="{sans}" build-server-full "$(hostname)" nopass

mkdir -p {certs_dir}
mv ./pki/ca.crt {certs_dir}/
mv ./pki/issued/* {certs_dir}/
mv ./pki/private/* {certs_dir}/
chown -R kube:kube {certs_dir}
chmod -R 0440 {certs_dir}/*

    """.format(
            primary_cn=MASTER_IP,
            sans=sans,
            certs_dir=KUBERNETES_CERTS_DIR
        ))


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
                    "--service_account_private_key_file=": K8S_TLS_CERT,
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

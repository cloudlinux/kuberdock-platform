from kubedock.updates import helpers
from kubedock.settings import MASTER_IP
from fabric.api import run, put
import json

configfile = """\
apiVersion: v1
kind: Config
users:
- name: kubelet
  user:
    token: {0}
clusters:
- name: local
  cluster:
     server: https://{1}:6443
     insecure-skip-tls-verify: true
contexts:
- context:
    cluster: local
    user: kubelet
  name: onlycontext
current-context: onlycontext
"""


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Generating new auth config file for nodes...')
    with open('/etc/kubernetes/kubelet_token.dat') as f:
        data = json.load(f)
    token = data['BearerToken']
    with open('/etc/kubernetes/configfile_for_nodes', 'w') as f:
        f.write(configfile.format(token, MASTER_IP))

    upd.print_log('Changing config files...')
    upd.print_log('1) controller-manager',
                  helpers.local('mv /etc/kubernetes/controller-manager.rpmnew '
                                '/etc/kubernetes/controller-manager'))
    upd.print_log('2) kube-apiserver')
    with open('/etc/kubernetes/apiserver') as f:
        data = f.read().replace('--portal_net', '--service-cluster-ip-range')
        data = data.replace('AutoProvision,LimitRanger', 'Lifecycle,NamespaceExists,LimitRanger,SecurityContextDeny,ServiceAccount')
        data = data.replace('--public_address_override', '--bind-address')
    with open('/etc/kubernetes/apiserver', 'w') as f:
        f.write(data)
    upd.print_log('Done.')

    upd.print_log('Trying to restart master kubernetes...')
    service, code = helpers.restart_master_kubernetes(with_enable=True)
    if service != 0:
        raise helpers.UpgradeError('Kubernetes not restarted. '
                                   'Service {0} code {1}'.format(service, code))
    else:
        upd.print_log('Deleting old token file',
                      helpers.local('rm -f /etc/kubernetes/kubelet_token.dat'))
    helpers.local('rm -f /etc/kubernetes/apiserver.rpmnew')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Replacing kubernetes with new kubernetes-node...')
    upd.print_log(
        helpers.remote_install(
            'kubernetes kubernetes-node-0.20.2-0.4.git323fde5.el7.centos.2',
            with_testing, 'swap'))

    upd.print_log('Replacing auth config with new...')
    put('/etc/kubernetes/configfile_for_nodes', '/etc/kubernetes/configfile')
    run("""sed -i '/^KUBELET_ARGS/ {s|--auth_path=/var/lib/kubelet/kubernetes_auth|--kubeconfig=/etc/kubernetes/configfile --register-node=false|}' /etc/kubernetes/kubelet""")

    run("""sed -i '/^KUBE_MASTER/ {s|http://|https://|}' /etc/kubernetes/config""")
    run("""sed -i '/^KUBE_MASTER/ {s|7080|6443|}' /etc/kubernetes/config""")
    run("""sed -i '/^KUBE_PROXY_ARGS/ {s|""|"--kubeconfig=/etc/kubernetes/configfile"|}' /etc/kubernetes/proxy""")
    service, res = helpers.restart_node_kubernetes(with_enable=True)
    if service != 0:
        raise helpers.UpgradeError('Failed to restart {0}. {1}'
                                   .format(service, res))
    else:
        upd.print_log(res)
        print run('rm -f /var/lib/kubelet/kubernetes_auth')


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade_node provided')

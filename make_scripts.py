import jinja2
from kubedock.settings import MASTER_IP, NODE_INET_IFACE, DOCKER_IF, ES_HOST

# NODE INSTALL SCRIPT
with open('kub_install.template') as f:
    r = jinja2.Template(f.read()).render(
        master_ip=MASTER_IP,
        inet_iface=NODE_INET_IFACE,
        docker_if=DOCKER_IF,
        es_host=ES_HOST,
    )

with open('kub_install.sh', 'wt') as f:
    f.write(r)

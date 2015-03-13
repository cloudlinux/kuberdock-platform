import jinja2
from kubedock.settings import MASTER_IP, NODE_INET_IFACE, ES_HOST

# MASTER INSTALL SCRIPT
with open('master_install.template') as f:
    r = jinja2.Template(f.read()).render(
        master_ip=MASTER_IP,
        inet_iface=NODE_INET_IFACE)

with open('master_install.sh', 'wt') as f:
    f.write(r)


# NODE INSTALL SCRIPT
with open('kub_install.template') as f:
    r = jinja2.Template(f.read()).render(
        master_ip=MASTER_IP,
        inet_iface=NODE_INET_IFACE,
        es_host=ES_HOST,
        )

with open('kub_install.sh', 'wt') as f:
    f.write(r)

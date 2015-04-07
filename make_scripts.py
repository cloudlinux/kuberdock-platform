import jinja2
from kubedock.settings import MASTER_IP, NODE_TOBIND_FLANNEL

# NODE INSTALL SCRIPT
with open('kub_install.template') as f:
    r = jinja2.Template(f.read()).render(
        master_ip=MASTER_IP,
        flannel_iface=NODE_TOBIND_FLANNEL,
    )

with open('kub_install.sh', 'wt') as f:
    f.write(r)

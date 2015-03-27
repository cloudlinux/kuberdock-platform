import jinja2
from kubedock.settings import MASTER_IP, NODE_INET_IFACE

# NODE INSTALL SCRIPT
with open('kub_install.template') as f:
    r = jinja2.Template(f.read()).render(
        master_ip=MASTER_IP,
        inet_iface=NODE_INET_IFACE,
        )

with open('kub_install.sh', 'wt') as f:
    f.write(r)

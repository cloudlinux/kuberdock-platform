from kubedock.updates import helpers
from fabric.api import run

DOCKERCLEANER = \
"""
#!/bin/bash
 
# the following command will not remove running containers, just displaying errors on them
docker rm $(docker ps -a -q) 
docker rm $(docker ps -f=status=exited -q)
docker rmi `docker images -qf 'dangling=true'`
docker rm -f `docker ps -a | grep Dead | awk '{print $1 }'`

EOF
"""

def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading nodes only')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrading nodes only')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Upgrading nodes with docker-cleaner.sh')
    run("""rm -f /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | grep -v "docker-cleaner.sh" | crontab - """)

def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Downgrading nodes with docker-cleaner.sh')
    run("cat > /var/lib/kuberdock/scripts/docker-cleaner.sh << 'EOF' {0}"
    .format(DOCKERCLEANER))
    run("""chmod +x /var/lib/kuberdock/scripts/docker-cleaner.sh""")
    run("""crontab -l | { cat; echo "0 */6 * * * /var/lib/kuberdock/scripts/docker-cleaner.sh"; } | crontab - """)

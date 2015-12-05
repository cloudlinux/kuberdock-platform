from kubedock.updates import helpers
from fabric.api import run


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading nodes only')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Downgrading nodes only')


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Upgrading nodes restricted ports iptables rules')
    run("""FIRST_IFACE=$(ip -o link show | awk -F: '$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;exit}}'); FIRST_IP=$(ip -o -4 address show $FIRST_IFACE|awk '/inet/ {sub(/\/.*$/, "", $4); print $4;exit;}'); NEWRULES=$(iptables-save | grep "A INPUT" | sed "s/-p tcp/-d $FIRST_IP -p tcp/g" | sed "s/^/iptables /" | sed "s/$/;/"); OLDRULESDEL=$(iptables-save | grep "A INPUT" | sed "s/-A/iptables -D/g" | sed "s/$/;/g"); eval $OLDRULESDEL; eval $NEWRULES""")


def downgrade_node(upd, with_testing, env,  exception, *args, **kwargs):
    upd.print_log('Downgrading nodes restricted ports iptables rules ')
    run("""NEWRULES=$(iptables-save | grep "A INPUT" | sed "s#-d [0-9]*\.[0-9]*\.[0-9]*\.[0-9]*/32 -p tcp#-p tcp#g" | sed "s/^/iptables /" | sed "s/$/;/"); OLDRULESDEL=$(iptables-save | grep "A INPUT" | sed "s/-A/iptables -D/g" | sed "s/$/;/g"); eval $OLDRULESDEL; eval $NEWRULES""")


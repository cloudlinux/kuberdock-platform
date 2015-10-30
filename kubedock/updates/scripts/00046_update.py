from fabric.api import run

SCRIPT_NEW = \
"""
CMD=$1
PUBLIC_IP=$2
IFACE=$3
# Commented because persistent ip breaks ip migration
# if old failed node will be booted again with NM
#nmcli g &> /dev/null
#if [ $? == 0 ];then
#    CONNECTION=$(nmcli -f UUID,DEVICE con | awk "/$IFACE/ {print \$1; exit}")
#    if [ -z $CONNECTION ];then
#        echo "No connection found for interface $IFACE"
#        exit 1
#    fi
#    if [ $CMD == 'add' ];then
#        nmcli con mod "$CONNECTION" +ipv4.addresses "$PUBLIC_IP/32"
#    else
#        nmcli con mod "$CONNECTION" -ipv4.addresses "$PUBLIC_IP/32"
#    fi
#fi
ip addr $CMD $PUBLIC_IP/32 dev $IFACE
if [ $CMD == 'add' ];then
    arping -I $IFACE -A $PUBLIC_IP -c 10 -w 1
fi
exit 0
EOF
"""

SCRIPT_OLD = \
"""
CMD=$1
PUBLIC_IP=$2
IFACE=$3
nmcli g &> /dev/null
if [ $? == 0 ];then
    CONNECTION=$(nmcli -f UUID,DEVICE con | awk "/$IFACE/ {print \$1; exit}")
    if [ -z $CONNECTION ];then
        echo "No connection found for interface $IFACE"
        exit 1
    fi
    if [ $CMD == 'add' ];then
        nmcli con mod "$CONNECTION" +ipv4.addresses "$PUBLIC_IP/32"
    else
        nmcli con mod "$CONNECTION" -ipv4.addresses "$PUBLIC_IP/32"
    fi
fi
ip addr $CMD $PUBLIC_IP/32 dev $IFACE
if [ $CMD == 'add' ];then
    arping -I $IFACE -A $PUBLIC_IP -c 10 -w 1
fi
exit 0
EOF
"""


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Change modify_ip.sh script...')
    upd.print_log(
        run("cat > /var/lib/kuberdock/scripts/modify_ip.sh << 'EOF' {0}"
            .format(SCRIPT_NEW))
    )


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Return back old modify_ip.sh script...')
    upd.print_log(
        run("cat > /var/lib/kuberdock/scripts/modify_ip.sh << 'EOF' {0}"
            .format(SCRIPT_OLD))
    )

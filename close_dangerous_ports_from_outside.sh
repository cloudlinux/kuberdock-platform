#!/bin/bash

PORT_TO_CLOSE=$1
if [ -z "$PORT_TO_CLOSE" ]
then
echo "Specify port to close please"
exit 1
else
echo "Port $PORT_TO_CLOSE will be closed"
fi

## Parce "kubectl get nodes" command
#cat template | tail -n +2 | cut -d ' ' -f 1 | while read -r TMP_LINE  
#do
#NODE_IP_ADDR=$(getent ahostsv4 $TMP_LINE | head -1 | cut -d ' ' -f 1)
#echo "$TMP_LINE:  $NODE_IP_ADDR"
#
#done

# Get master ip address by querying the first network interface
FIRST_IFACE=$(ip -o link show | awk -F: '$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;exit}}')
echo "Your external network interface is $FIRST_IFACE"
MASTER_IP_ADDR=$(ip addr show $FIRST_IFACE | grep "inet " | awk '{ print $2 }' | cut -d "/" -f 1)
echo "Your external network address is $MASTER_IP_ADDR"

# Form the head of the temporary script to be sent to nodes via ssh
echo "#!/bin/bash" > /tmp/close_port_on_nodes.sh
chmod +x /tmp/close_port_on_nodes.sh
echo "PORTTOCLOSE=$PORT_TO_CLOSE" >> /tmp/close_port_on_nodes.sh

# Add lines replacing single quote with QQQQQQQ
echo '
FIRST_IFACE=$(ip -o link show | awk -F: QQQQQQQ$3 ~ /LOWER_UP/ {gsub(/ /, "", $2); if ($2 != "lo"){print $2;exit}}QQQQQQQ)

echo "Your external network interface is $FIRST_IFACE"

iptables-save | grep $FIRST_IFACE | grep "\-p tcp \-m tcp \-\-dport $PORTTOCLOSE \-m state \-\-state NEW,ESTABLISHED \-j ACCEPT$" | sed "s/-A/-D/g" | while read -r line  
do
echo "Deletting rule:  $line"
iptables $line
done

echo "Deletting a REJECT rule"
iptables -D INPUT -i $FIRST_IFACE -p tcp --dport=$PORTTOCLOSE -j REJECT

echo "Adding ACCEPT rules, generated with a loop"
' >> /tmp/close_port_on_nodes.sh

#########_FILL_THE_ACCEPT_RULE_LINES_####################################

# Parce "kubectl get nodes" command
kubectl get nodes | tail -n +2 | cut -d ' ' -f 1 | while read -r TMP_LINE  
do
NODE_IP_ADDR=$(getent ahostsv4 $TMP_LINE | head -1 | cut -d ' ' -f 1)
echo "$TMP_LINE:  $NODE_IP_ADDR"
# Adding ACCEPT rules to a temporary script
echo "iptables -A INPUT -i \$FIRST_IFACE -p tcp -s $NODE_IP_ADDR/32 --dport=\$PORTTOCLOSE -m state --state NEW,ESTABLISHED -j ACCEPT" >> /tmp/close_port_on_nodes.sh
done
echo "iptables -A INPUT -i \$FIRST_IFACE -p tcp -s $MASTER_IP_ADDR/32 --dport=\$PORTTOCLOSE -m state --state NEW,ESTABLISHED -j ACCEPT" >> /tmp/close_port_on_nodes.sh
#########################################################################

# Adding a REJECT rule to a temporary script

echo '
echo "Adding the last latest reject rule"
iptables -A INPUT -i $FIRST_IFACE -p tcp --dport=$PORTTOCLOSE -j REJECT' >> /tmp/close_port_on_nodes.sh

# Getting single qoutes back
sed -i "s/QQQQQQQ/'/g" /tmp/close_port_on_nodes.sh

# Delivering the temporary scropt do nodes via ssh
kubectl get nodes | tail -n +2 | cut -d ' ' -f 1 | while read -r TMP_HOST  
do
echo "Delivering to $TMP_HOST"
ssh root@$TMP_HOST -i /var/lib/nginx/.ssh/id_rsa 'bash -s' < /tmp/close_port_on_nodes.sh

done


# Should we clean it? OK, not now.
#rm /tmp/close_port_on_nodes.sh


from kubedock.kapi.nodes import handle_nodes, process_rule
from kubedock.nodes.models import Node
from kubedock.settings import MASTER_IP, PORTS_TO_RESTRICT


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Allow master to access ElasticSearch on nodes')
    nodes = [n for n, in Node.query.values(Node.ip)]
    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='insert', port=port,
                     target='ACCEPT', source=MASTER_IP, append_reject=False)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Revert "Allow master to access ElasticSearch on nodes"')
    nodes = [n for n, in Node.query.values(Node.ip)]
    for port in PORTS_TO_RESTRICT:
        handle_nodes(process_rule, nodes=nodes, action='delete', port=port,
                     target='ACCEPT', source=MASTER_IP, append_reject=False)

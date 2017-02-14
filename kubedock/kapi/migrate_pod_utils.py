"""Utilities to migrate pods from one node to another if those pods are binded
to a node.
"""
from flask import current_app

from kubedock.core import db
from kubedock.kapi import node_utils, node_utils_aws, service_pods
from kubedock.kapi.podcollection import PodCollection
from kubedock.nodes.models import Node
from kubedock.pods.models import PersistentDisk, Pod
from kubedock.settings import AWS, WITH_TESTING
from kubedock.users.models import User
from kubedock.utils import NODE_STATUSES, POD_STATUSES


def change_pods_node_selectors(from_node, to_node):
    """Changes node selector of pods from 'from_node' to 'to_node'
    :param from_node: node which has binded pods (object of model Node)
    :param to_node: to this node should be binded pods. Also object of model
        Node
    """
    current_app.logger.debug(
        "Starting pods migration from '{}' to '{}'".format(
            from_node.hostname, to_node.hostname
        )
    )
    pc = PodCollection()
    internal_user = User.get_internal()
    PersistentDisk.get_by_node_id(from_node.id).update(
        {PersistentDisk.node_id: to_node.id},
        synchronize_session=False
    )
    dbpods = Pod.query.filter(
        Pod.owner_id != internal_user.id,
        Pod.status != 'deleted'
    ).all()

    for pod in dbpods:
        if pod.pinned_node != from_node.hostname:
            continue
        current_app.logger.debug(
            "Update pod ({0}) config to use new node '{1}'".format(
                pod.id, to_node.hostname
            )
        )
        pc.update(
            pod.id, {'command': 'change_config', 'node': to_node.hostname}
        )
        k8s_pod = pc._get_by_id(pod.id)
        if k8s_pod.status in (POD_STATUSES.stopping, POD_STATUSES.stopped):
            continue

        current_app.logger.debug(
            "Restarting pod after migration: {}".format(pod.id))
        try:
            pc.update(pod.id, {'command': 'redeploy'})
            # current_app.logger.debug("Skip restarting")
        except:
            current_app.logger.exception(
                "Failed to redeploy pod after migration: {}".format(pod.id)
            )


def manage_failed_aws_node(node_hostname, ssh, deploy_func):
    current_app.logger.debug(
        "Try to migrate from failed node '{0}'".format(node_hostname)
    )

    failed_node = db.session.query(Node).filter(
        Node.hostname == node_hostname
    ).first()
    if not failed_node:
        current_app.logger.error(
            "Node '{0}' not found in DB".format(node_hostname)
        )
        return

    reserve_node_hostname, reserve_node_ip, reserve_node_fast = \
        node_utils_aws.spawn_reserving_node(node_hostname)
    current_app.logger.debug(
        'Created reserve node: {0}'.format(reserve_node_hostname)
    )

    current_app.logger.debug('Setting failed node ({0}) '
                             'as unschedulable'.format(node_hostname))
    node_utils.set_node_schedulable_flag(node_hostname, False)

    current_app.logger.debug(
        'Add node to database {0}'.format(reserve_node_hostname)
    )
    reserve_node = Node(
        ip=reserve_node_ip,
        hostname=reserve_node_hostname,
        kube_id=failed_node.kube_id,
        state=NODE_STATUSES.pending,
    )
    reserve_node = node_utils.add_node_to_db(reserve_node)

    current_app.logger.debug('Waiting for node is running '
                             '{0}'.format(reserve_node_hostname))
    node_utils_aws.wait_node_running(reserve_node_hostname)
    current_app.logger.debug(
        'Node is running {0}'.format(reserve_node_hostname)
    )
    current_app.logger.debug('Waiting for node is accessible '
                             '{0}'.format(reserve_node_hostname))
    target_ssh = node_utils_aws.wait_node_accessible(reserve_node_hostname)
    current_app.logger.debug(
        'Node is accessible {0}'.format(reserve_node_hostname)
    )

    current_app.logger.debug(
        "Create logging pod for '{0}'".format(reserve_node_hostname)
    )
    ku = User.get_internal()
    log_pod = service_pods.create_logs_pod(reserve_node_hostname, ku)

    current_app.logger.debug(
        "Deploying reserving node '{0}'".format(reserve_node_hostname)
    )
    current_app.logger.debug(
        'Fast deploy' if reserve_node_fast else 'Slow deploy'
    )
    deploy_func(reserve_node_fast, reserve_node.id, log_pod['podIP'])

    if ssh:
        current_app.logger.debug(
            "Stopping k8s services on node '{0}'".format(node_hostname)
        )
        node_utils.stop_node_k8_services(ssh)
    else:
        current_app.logger.warning(
            "Failed node '{0}' is not accessible via ssh. "
            "Can't stop k8s services on the node.".format(node_hostname))

    current_app.logger.debug(
        "Moving storage from '{0}' to '{1}'".format(
            node_hostname, reserve_node_hostname)
    )
    if not node_utils.move_aws_node_storage(ssh, target_ssh,
                                            failed_node, reserve_node):
        current_app.logger.error(
            "Failed to move aws storage from '{0}' to '{1}'".format(
                node_hostname, reserve_node_hostname)
        )
        return

    current_app.logger.debug(
        "Changing pods selectors to node '{0}'".format(reserve_node_hostname)
    )
    change_pods_node_selectors(failed_node, reserve_node)

    current_app.logger.debug(
        'Delete node from KuberDock {0}'.format(node_hostname)
    )
    try:
        node_utils.revoke_celery_node_install_task(failed_node)
        node_utils.delete_node_from_db(failed_node)
        res = node_utils.remove_node_from_k8s(node_hostname)
        if res['status'] == 'Failure' and res['code'] != 404:
            raise Exception('Failed to remove node {0} '
                            'from Kubernetes'.format(node_hostname))
        node_utils.remove_node_install_log(node_hostname)
        node_utils.cleanup_node_network_policies(node_hostname)
        service_pods.delete_logs_pod(node_hostname)
        node_utils_aws.terminate_node(node_hostname)
    except Exception as e:
        current_app.logger.error(
            "Failed to delete node '{0}': {1}".format(node_hostname, e)
        )

    try:
        db.session.commit()
    except:
        db.session.rollback()
        raise

    current_app.logger.error("Migration to node '{0}' completed "
                             "successfully".format(reserve_node_hostname))


def manage_failed_node(node_hostname, ssh, deploy_func):
    """Does some actions with the failed node if it is possible.
    Now works only for AWS setup configured with reserved nodes:
    if some node has failed, then take one from reserve, move there storage
    of failed node.
    """
    if AWS:
        manage_failed_aws_node(node_hostname, ssh, deploy_func)
    else:
        current_app.logger.warning(
            'Failed node detected ({0}), '
            'but no recovery procedure available.'.format(node_hostname))

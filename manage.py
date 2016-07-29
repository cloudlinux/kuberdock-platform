import os
import sys
import pytz
import logging
import string
import time
from random import choice
from datetime import datetime
import json
import argparse

from ipaddress import IPv4Network

from kubedock.api import create_app
from kubedock.exceptions import APIError
from kubedock.kapi.nodes import create_node, delete_node
from kubedock.validation import check_node_data
from kubedock.utils import UPDATE_STATUSES, NODE_STATUSES
from kubedock.core import db
from kubedock.models import User, Pod
from kubedock.pods.models import PersistentDisk
from kubedock.billing.models import Package, Kube
from kubedock.billing.fixtures import add_kubes_and_packages
from kubedock.rbac.fixtures import add_permissions
from kubedock.users.fixtures import add_users_and_roles
from kubedock.rbac.models import Role
from kubedock.system_settings.fixtures import add_system_settings
from kubedock.notifications.fixtures import add_notifications
from kubedock.static_pages.fixtures import generate_menu
from kubedock.settings import NODE_CEPH_AWARE_KUBERDOCK_LABEL, WITH_TESTING
from kubedock.updates.models import Updates
from kubedock.nodes.models import Node, NodeFlag, NodeFlagNames
from kubedock.updates.kuberdock_upgrade import get_available_updates
from kubedock.updates.helpers import get_maintenance
from kubedock import tasks
from kubedock.kapi import licensing
from kubedock.kapi.pstorage import check_namespace_exists
from kubedock.kapi import ippool
from kubedock.kapi.node_utils import (
    get_one_node, extend_ls_volume, get_ls_info)

from flask.ext.script import Manager, Shell, Command, Option, prompt_pass
from flask.ext.script.commands import InvalidCommand
from flask.ext.migrate import Migrate, MigrateCommand, upgrade, stamp
from flask.ext.migrate import migrate as migrate_func

from sqlalchemy.orm.exc import NoResultFound

logging.getLogger("requests").setLevel(logging.WARNING)

WAIT_TIMEOUT = 10 * 60  # 10 minutes
WAIT_TROUBLE_TIMEOUT = 3 * 60  # 3 minutes
WAIT_RETRY_DELAY = 5  # seconds


class Creator(Command):
    option_list = (Option('password'),)

    def run(self, password):
        db.drop_all()
        db.create_all()

        # WARNING:
        # if you edit this method, make analogous changes in
        # kubedock.testutils.fixtures.initial_fixtures
        # TODO: merge two methods in one

        now = datetime.utcnow()
        now.replace(tzinfo=pytz.utc)
        available_updates = get_available_updates()
        if available_updates:
            last_upd = Updates.create(fname=available_updates[-1],
                                      status=UPDATE_STATUSES.applied,
                                      log='Applied at createdb stage.',
                                      start_time=now, end_time=now)
            db.session.add(last_upd)
        db.session.commit()

        add_kubes_and_packages()

        add_system_settings()

        add_notifications()

        add_permissions()

        add_users_and_roles(password)

        generate_menu()

        # Fix packages id next val
        db.engine.execute("SELECT setval('packages_id_seq', 1, false)")

        stamp()


class Updater(Command):
    def run(self):
        migrate_func()
        upgrade()


class WaitTimeoutException(Exception):
    pass


class WaitTroubleException(Exception):
    pass


def wait_for_nodes(nodes_list, timeout, verbose=False):
    timeout = timeout or WAIT_TIMEOUT

    def _print(msg):
        if verbose:
            print msg

    wait_end = time.time() + timeout
    host_list = list(set(nodes_list))
    nodes_in_trouble = {}

    while host_list:
        if time.time() > wait_end:
            remaining_nodes = [Node.get_by_name(nhost) for nhost in nodes_list]
            raise WaitTimeoutException(
                "These nodes did not become 'running' in a given timeout {}s:\n"
                "{}".format(timeout, remaining_nodes))

        time.sleep(WAIT_RETRY_DELAY)

        db.session.expire_all()
        for nhost in host_list[:]:  # Do not modify list while iterating it
            db_node = Node.get_by_name(nhost)
            if db_node is None:
                raise WaitTimeoutException("Node `%s` was not found." % nhost)
            k8s_node = get_one_node(db_node.id)
            state = k8s_node['status']
            if state == NODE_STATUSES.troubles:
                if nhost not in nodes_in_trouble:
                    nodes_in_trouble[nhost] = time.time() + WAIT_TROUBLE_TIMEOUT
                if time.time() > nodes_in_trouble[nhost]:
                    raise WaitTroubleException(
                        "Node '{}' went into troubles and still in troubles "
                        "state after '{}' seconds.".format(
                            nhost, WAIT_TROUBLE_TIMEOUT))
                else:
                    _print("Node '{}' state is 'troubles' but acceptable "
                           "troubles timeout '{}'s is not reached yet..".format(
                            nhost, WAIT_TROUBLE_TIMEOUT))
            elif state == NODE_STATUSES.running:
                host_list.remove(nhost)
            else:
                _print("Node '{}' state is '{}', continue waiting..".format(
                    nhost, state))


class NodeManager(Command):
    option_list = [
        Option('--hostname', dest='hostname', required=True),
        Option('--kube-type', dest='kube_type', required=False),
        Option('--do-deploy', dest='do_deploy', action='store_true'),
        Option('--wait', dest='wait', action='store_true'),
        Option('--timeout', dest='timeout', required=False, type=int),
        Option('-t', '--testing', dest='testing', action='store_true'),
        Option('--docker-options', dest='docker_options'),
        Option('--ebs-volume', dest='ebs_volume', required=False),
        Option('--localstorage-device', dest='ls_device', required=False),
        Option('-v', '--verbose', dest='verbose', required=False,
               action='store_true'),
    ]

    def run(self, hostname, kube_type, do_deploy, wait, timeout, testing,
            docker_options, ebs_volume, ls_device, verbose):

        if kube_type is None:
            kube_type_id = Kube.get_default_kube_type()
        else:
            kube_type = Kube.get_by_name(kube_type)
            if kube_type is None:
                raise InvalidCommand('Kube type with name `{0}` not '
                                     'found.'.format(kube_type))
            kube_type_id = kube_type.id

        options = None
        testing = testing or WITH_TESTING
        if docker_options is not None:
            options = {'DOCKER': docker_options}

        if get_maintenance():
            raise InvalidCommand(
                'Kuberdock is in maintenance mode. Operation canceled'
            )
        try:
            check_node_data({'hostname': hostname, 'kube_type': kube_type_id})
            if ls_device:
                ls_device = [ls_device]
            res = create_node(None, hostname, kube_type_id, do_deploy, testing,
                              options=options,
                              ls_devices=ls_device, ebs_volume=ebs_volume)
            print(res.to_dict())
            if wait:
                wait_for_nodes([hostname, ], timeout, verbose)
        except Exception as e:
            raise InvalidCommand("Node management error: {0}".format(e))


class DeleteNodeCmd(Command):
    option_list = (
        Option('--hostname', dest='hostname', required=True),
    )

    def run(self, hostname):
        node = db.session.query(Node).filter(Node.hostname == hostname).first()
        if node is None:
            raise InvalidCommand(u'Node "{0}" not found'.format(hostname))

        PersistentDisk.get_by_node_id(node.id).delete(
            synchronize_session=False)
        delete_node(node=node, force=True)


class WaitForNodes(Command):
    """Wait for nodes to become ready.
    """
    option_list = (
        Option('--nodes', dest='nodes', required=True),
        Option('--timeout', dest='timeout', required=False, type=int),
        Option('--verbose', dest='verbose', required=False,
               action='store_true'),
    )

    def run(self, nodes, timeout, verbose):
        nodes_list = nodes.split(',')
        wait_for_nodes(nodes_list, timeout, verbose)


def generate_new_pass():
    return ''.join(choice(string.digits + string.letters) for _ in range(10))


class ResetPass(Command):

    chars = string.digits + string.letters
    option_list = (
        Option('--generate', dest='generate', default=False,
               action='store_true'),
        Option('--set', dest='new_password', required=False),
    )

    def run(self, generate, new_password):
        print "Change password for admin."
        u = db.session.query(User).filter(User.username == 'admin').first()
        new_pass = None
        if generate:
            new_pass = generate_new_pass()
            print "New password: {}".format(new_pass)
        elif new_password:
            new_pass = new_password
        else:
            for i in range(3):
                first_attempt = prompt_pass("Enter new password")
                second_attempt = prompt_pass("Retype new password")
                if first_attempt == second_attempt:
                    new_pass = first_attempt
                    break
                print "Sorry, passwords do not match."
        if new_pass:
            u.password = new_pass
            db.session.commit()
            print "Password has been changed"


class NodeFlagCmd(Command):
    """Manage flags for a node"""
    option_list = (
        Option('-n', '--nodename', dest='nodename', required=True,
               help='Node host name'),
        Option('-f', '--flagname', dest='flagname', required=True,
               help='Flag name to change'),
        Option('--value', dest='value', required=False,
               help='Flag value to set'),
        Option('--delete', dest='delete', required=False, default=False,
               action='store_true', help='Delete the flag'),
    )

    def run(self, nodename, flagname, value, delete):
        node = Node.get_by_name(nodename)
        if not node:
            raise InvalidCommand(u'Node "{0}" not found'.format(nodename))
        if delete:
            NodeFlag.delete_by_name(node.id, flagname)
            print u'Node flag "{0}" was deleted'.format(flagname)
            return
        NodeFlag.save_flag(node.id, flagname, value)
        if flagname == NodeFlagNames.CEPH_INSTALLED:
            tasks.add_k8s_node_labels(
                node.hostname,
                {NODE_CEPH_AWARE_KUBERDOCK_LABEL: "True"}
            )
            check_namespace_exists(node.ip)
        print u'Node "{0}": flag "{1}" was set to "{2}"'.format(
            nodename, flagname, value)


class NodeInfoCmd(Command):
    """Manage flags for a node"""
    option_list = (
        Option('-n', '--nodename', dest='nodename', required=True,
               help='Node host name'),
    )

    def run(self, nodename):
        node = Node.get_by_name(nodename)
        if not node:
            raise InvalidCommand(u'Node "{0}" not found'.format(nodename))
        print json.dumps(node.to_dict())


class AuthKey(Command):
    """Returns auth key. Generates it if not created yet"""

    def run(self):
        try:
            key = licensing.get_auth_key()
        except APIError:
            # Actually this case is never happens because generate_auth_key()
            # called even earlie, during modules import. But I leave it here too
            # for extra safety
            key = licensing.generate_auth_key()
        print key


class CreateIPPool(Command):
    """ Creates IP pool
    """
    option_list = (
        Option('-s', '--subnet', dest='subnet', required=True,
               help='Network with mask'),
        Option('-e', '--exclude', dest='exclude', required=False,
               help='Excluded ips'),
        Option('-i', '--include', dest='include', required=False,
               help='Included ips'),
        Option('--node', dest='node', required=False,
               help='Node name'),
    )

    def run(self, subnet, exclude, include, node=None):
        if exclude and include:
            raise InvalidCommand('Can\'t specify both -e and -i')

        if include:
            to_include = ippool.IpAddrPool().parse_autoblock(include)
            net = IPv4Network(unicode(subnet))
            hosts = {str(i) for i in net.hosts()}
            # .hosts() does not include the network address
            hosts.add(str(net.network_address))
            exclude = ','.join(hosts - to_include)

        ippool.IpAddrPool().create({
            'network': subnet.decode(),
            'autoblock': exclude,
            'node': node
        })


class DeleteIPPool(Command):
    """ Deletes IP pool
    """
    option_list = (
        Option('-s', '--subnet', dest='subnet', required=True,
               help='Network with mask'),
    )

    def run(self, subnet):
        ippool.IpAddrPool().delete(subnet.decode())


class ListIPPool(Command):
    """ Deletes IP pool
    """
    option_list = tuple()

    def run(self):
        print(json.dumps(ippool.IpAddrPool().get()))


class CreateUser(Command):
    """ Creates a new user
    """

    option_list = (
        Option('-u', '--username', dest='username', required=True,
               help='User name'),
        Option('-p', '--password', dest='password', required=False,
               help='User password'),
        Option('-r', '--rolename', dest='rolename', required=True,
               help='User role name'),
    )

    def run(self, username, password, rolename):
        try:
            role = Role.filter_by(rolename=rolename).one()
        except NoResultFound:
            raise InvalidCommand('Role with name `%s` not found' % rolename)

        if User.filter_by(username=username).first():
            raise InvalidCommand('User `%s` already exists' % username)

        if not password:
            password = generate_new_pass()
            print "New password: {}".format(password)

        u = User.create(username=username, password=password, role=role,
                        active=True, package_id=0)
        db.session.add(u)
        db.session.commit()


class AddPredefinedApp(Command):
    """Adds a predefined app
    """

    option_list = (
        Option('-n', '--name', dest='name', required=True,
               help="Predefined app's name"),
        Option('-t', '--template', dest='template', required=True,
               help="Predefined app's template"),
        Option('-u', '--user', dest='username', required=False,
               help='User name'),
        Option('-o', '--origin', dest='origin', required=False,
               help='Origin'),
        Option('-f', '--no-validation', dest='no_validation',
               action='store_true'),
    )

    def run(self, name, template, username, origin, no_validation):
        from kubedock.kapi.predefined_apps import PredefinedApps

        if username is None:
            role = Role.filter_by(rolename='Admin').first()
            user = User.filter_by(role=role).first()
            if not user:
                raise InvalidCommand('No username was specified, so user with '
                                     'Admin role was searched but not found.')
        else:
            user = User.filter_by(username=username).first()
            if not user:
                raise InvalidCommand('User with `{0}` username not '
                                     'found'.format(username))

        try:
            with open(template, 'r') as tf:
                template_data = tf.read()
        except IOError as err:
            raise InvalidCommand("Can not load template: %s" % err)

        result = PredefinedApps(user).create(
            name=name,
            template=template_data,
            origin=origin or 'kuberdock',
            validate=not no_validation
        )
        print(result)


node_ls_manager = Manager()


def _positive_int_checker(value):
    """Type checker for argparse. Accepts only positive integers."""
    ivalue = int(value)
    if ivalue <= 0:
        raise argparse.ArgumentTypeError(
            '{} is not positive integer'.format(value)
        )
    return ivalue


class NodeLSAddVolume(Command):
    """Adds a volume to node's locastorage"""
    option_list = [
        Option('--hostname', dest='hostname', required=True),
        Option(
            '--ebs-volume', dest='ebs_volume', required=False,
            help='Name of existing EBS volume (only for AWS-clusters)'
        ),
        Option(
            '--size', dest='size', required=False, type=_positive_int_checker,
            help='Size (GB) for new EBS volume (only for AWS-clusters)'
        ),
        Option(
            '--devices', dest='devices', required=False,
            help='Comma separated list of block devices already attached to '
                 'the node'
        ),
    ]

    def run(self, hostname, ebs_volume, size, devices):
        if get_maintenance():
            raise InvalidCommand(
                'Kuberdock is in maintenance mode. Operation canceled'
            )
        if size is not None and size <= 0:
            raise InvalidCommand(
                'Invalid size value (must be > 0): {}'.format(size)
            )
        if devices:
            devices = devices.split(',')
        ok, message = extend_ls_volume(
            hostname, devices=devices, ebs_volume=ebs_volume, size=size
        )
        if not ok:
            raise InvalidCommand(u'Failed to extend LS: {}'.format(message))
        print 'Operation performed successfully'


class NodeLSGetInfo(Command):
    """Returns information about local storage on a node"""
    option_list = [
        Option('--hostname', dest='hostname', required=True),
    ]

    def run(self, hostname):
        try:
            result = get_ls_info(hostname, raise_on_error=True)
        except APIError as err:
            raise InvalidCommand(str(err))
        print json.dumps(result)


node_ls_manager.add_command('add-volume', NodeLSAddVolume)
node_ls_manager.add_command('get-info', NodeLSGetInfo)


app = create_app(fake_sessions=True)
manager = Manager(app, with_default_commands=False)
directory = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                         'kubedock',
                         'updates',
                         'kdmigrations')
migrate = Migrate(app, db, directory)


def make_shell_context():
    return dict(app=app, db=db, User=User, Pod=Pod, Package=Package, Kube=Kube)

manager.add_command('shell', Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)
manager.add_command('createdb', Creator())
manager.add_command('updatedb', Updater())
manager.add_command('add-node', NodeManager())
manager.add_command('delete-node', DeleteNodeCmd())
manager.add_command('wait-for-nodes', WaitForNodes())
manager.add_command('reset-password', ResetPass())
manager.add_command('node-flag', NodeFlagCmd())
manager.add_command('node-info', NodeInfoCmd())
manager.add_command('auth-key', AuthKey())
manager.add_command('create-ip-pool', CreateIPPool())
manager.add_command('delete-ip-pool', DeleteIPPool())
manager.add_command('list-ip-pools', ListIPPool())
manager.add_command('create-user', CreateUser())
manager.add_command('add-predefined-app', AddPredefinedApp())
manager.add_command('node-storage', node_ls_manager)


if __name__ == '__main__':
    try:
        manager.run()
    except InvalidCommand as err:
        sys.stderr.write(str(err))
        sys.exit(1)

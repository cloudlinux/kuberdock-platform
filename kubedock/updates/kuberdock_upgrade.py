#!/usr/bin/python

import os
import re
import yum
import sys
import json
import argparse
import requests
import sqlalchemy.orm.exc
import subprocess
from datetime import datetime
from importlib import import_module
from fabric.api import env, output
from sqlalchemy import or_
from flask.ext.migrate import Migrate

if __name__ == '__main__' and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))))

from kubedock import settings
from kubedock.api import create_app
from kubedock.updates import helpers
from kubedock.updates.models import Updates, db
from kubedock.nodes.models import Node
from kubedock.utils import UPDATE_STATUSES, get_api_url


class CLI_COMMANDS:
    upgrade = 'upgrade'
    resume_upgrade = 'resume-upgrade'
    set_maintenance = 'set-maintenance'
    set_node_schedulable = 'set-node-schedulable'
    # not documented for user. It's for internal use only:
    after_reload = '--after-reload'


FAILED_MESSAGE = """\
Cluster was left in a maintenance mode, \
please contact to support team for help. \
Use {0} {1} on|off to manually switch \
cluster work mode (careful!)\
""".format(os.path.basename(__file__), CLI_COMMANDS.set_maintenance)


SUCCESSFUL_DOWNGRADE_MESSAGE = """\
Downgrade looks successful but cluster was left in maintenance mode for you \
to ensure that all works properly. \
Use {0} {1} on|off to manually switch \
cluster work mode (careful!)\
""".format(os.path.basename(__file__), CLI_COMMANDS.set_maintenance)


def get_available_updates():
    patt = re.compile(r'^[0-9]{5}_update\.py$')
    return sorted(filter(patt.match, os.listdir(settings.UPDATES_PATH)))


def get_applied_updates():
    return sorted(
        [i.fname for i in Updates.query.filter_by(
            status=UPDATE_STATUSES.applied).all()])


def set_schedulable(node_id, value, upd=None):
    """
    Set node unschedulable property
    :param node_id: node id in kubernetes (now it's node hostname)
    :param value: boolean, true if node schedulable
    :param upd: db update record, if present print logs there too
    :return: boolean true if successful
    """
    url = get_api_url('nodes', node_id, namespace=False)
    try_times = 100
    for i in range(try_times):
        try:
            node = requests.get(url).json()
            node['spec']['unschedulable'] = not value
            res = requests.put(url, data=json.dumps(node))
        except (requests.RequestException, ValueError):
            continue
        if res.ok:
            return True
    msg = "Failed to set node schedulable mode in kubernetes after {0} tries"\
          ". You can try later to set mode again manually with {1} on|off"\
          .format(try_times, CLI_COMMANDS.set_node_schedulable)
    if upd:
        upd.print_log(msg)
    else:
        print msg
    return False


def load_update(upd):
    """
    Loads 000XX_update.py scripts and mark update as started. Check that all
    imported functions are exists and callable.
    :param upd: filename of loaded script
    :return: 5 values:
        1) in_db_update record obj
        2) upgrade_func
        3) downgrade_func
        4) upgrade_node_func or None
        5) downgrade_node_func or None (Must present if upgrade_node_func is)
    """
    try:
        module = import_module('scripts.' + upd.rsplit('.py')[0])
    except ImportError as e:
        print >> sys.stderr, 'Error importing update script {0}. {1}'.format(
            upd, e.__repr__())
        return None, None, None, None, None

    in_db_update = Updates.query.get(upd) or \
                   Updates.create(fname=upd,
                                  status=UPDATE_STATUSES.started,
                                  start_time=datetime.utcnow())
    in_db_update.start_time = datetime.utcnow()
    db.session.add(in_db_update)
    db.session.commit()

    if hasattr(module, 'upgrade') and callable(module.upgrade) and \
       hasattr(module, 'downgrade') and callable(module.downgrade):
        upgrade_func = module.upgrade
        downgrade_func = module.downgrade
    else:
        in_db_update.print_log(
            'Error. No upgrade/downgrade functions found in script.')
        return None, None, None, None, None

    downgrade_node_func = None
    if hasattr(module, 'upgrade_node') and callable(module.upgrade_node):
        upgrade_node_func = module.upgrade_node
        if hasattr(module, 'downgrade_node') and callable(module.downgrade_node):
            downgrade_node_func = module.downgrade_node
        else:
            in_db_update.print_log(
                'Error: No downgrade_node function found in script.')
            return None, None, None, None, None
    else:
        upgrade_node_func = None

    return in_db_update, upgrade_func, downgrade_func, upgrade_node_func,\
        downgrade_node_func


def upgrade_nodes(upgrade_node, downgrade_node, db_upd, with_testing,
                  evict_pods=False):
    """
    Do upgrade_node function on each node and fallback to downgrade_node
    if errors.
    :param upgrade_node: callable in current upgrade script
    :param downgrade_node: callable in current upgrade script
    :param db_upd: db record of current update script
    :param with_testing: Boolean, whether testing repo is enabled during upgrade
    :return: Boolean, True if all nodes upgraded, False if one or more failed.
    """
    if helpers.set_evicting_timeout('99m0s'):
        db_upd.print_log("Can't set pods evicting interval.")
        return False

    successful = True
    if db_upd.status == UPDATE_STATUSES.nodes_failed:
        nodes = db.session.query(Node).filter(
            or_(Node.upgrade_status == UPDATE_STATUSES.failed,
                Node.upgrade_status == UPDATE_STATUSES.failed_downgrade)).all()
    else:
        nodes = db.session.query(Node).all()

    db_upd.status == UPDATE_STATUSES.nodes_started
    db_upd.print_log('Started nodes upgrade. {0} nodes will be upgraded...'
                     .format(len(nodes)))
    for node in nodes:
        if not set_schedulable(node.hostname, False, db_upd):
            successful = False
            if not node.upgrade_status == UPDATE_STATUSES.failed_downgrade:
                node.upgrade_status = UPDATE_STATUSES.failed
            db.session.add(node)
            db.session.commit()
            db_upd.print_log('Failed to make node {0} unschedulable. Skip node.'
                             .format(node.hostname))
            continue

        env.host_string = node.hostname
        node.upgrade_status = UPDATE_STATUSES.started
        db_upd.print_log('Upgrading {0} ...'.format(node.hostname))
        try:
            upgrade_node(db_upd, with_testing, env)
        except Exception as e:
            successful = False
            node.upgrade_status = UPDATE_STATUSES.failed
            db_upd.print_log('Exception "{0}" during upgrade node {1}. {2}'
                             .format(e.__class__.__name__, node.hostname, e))
            try:
                downgrade_node(db_upd, with_testing, env, e)
            except Exception as e:
                node.upgrade_status = UPDATE_STATUSES.failed_downgrade
                db_upd.print_log(
                    'Exception "{0}" during downgrade node {1}. {2}'
                    .format(e.__class__.__name__, node.hostname, e))
            else:
                # Check here if new master is compatible with old nodes
                # set_schedulable(node.hostname, True, db_upd)
                db_upd.print_log('Node {0} successfully downgraded'
                                 .format(node.hostname))
        else:
            set_schedulable(node.hostname, True, db_upd)
            node.upgrade_status = UPDATE_STATUSES.applied
            db_upd.print_log('Node {0} successfully upgraded'
                             .format(node.hostname))
        finally:
            db.session.add(node)
            db.session.commit()

    if helpers.set_evicting_timeout('5m0s'):
        db_upd.print_log("Can't bring back old pods evicting interval.")
    return successful


def upgrade_master(upgrade_func, downgrade_func, db_upd, with_testing):
    """
    :return: True if success else False
    """
    if db_upd.status == UPDATE_STATUSES.nodes_failed:
        # only nodes upgrade needed case
        return True
    db_upd.status = UPDATE_STATUSES.started
    db_upd.print_log('Started master upgrade...')
    try:
        # TODO return boolean whether this upgrade is compatible with
        # not upgraded nodes. For now - always is.
        upgrade_func(db_upd, with_testing)
    except Exception as e:
        db_upd.status = UPDATE_STATUSES.failed
        db_upd.print_log('Error in update script '
                         '{0}. {1}. Starting downgrade...'
                         .format(db_upd.fname, e.__repr__()))
        try:
            downgrade_func(db_upd, with_testing, e)
        except Exception as e:
            db_upd.status = UPDATE_STATUSES.failed_downgrade
            db_upd.print_log('Error downgrading script {0}. {1}'
                             .format(db_upd.fname, e.__repr__()))
            db_upd.print_log(FAILED_MESSAGE)
        else:
            helpers.restart_service(settings.KUBERDOCK_SERVICE)
            db_upd.print_log(SUCCESSFUL_DOWNGRADE_MESSAGE)
        return False
    db_upd.status = UPDATE_STATUSES.master_applied
    return True


def do_cycle_updates(with_testing=False):
    """
    :return: False if no errors or script name at which was error
    """
    to_apply = get_available_updates()
    last = get_applied_updates()
    if last:
        to_apply = to_apply[to_apply.index(last[-1])+1:]
    is_failed = False
    if not to_apply:
        print 'There is no new upgrade scripts to apply. ' \
              'Maintenance mode is now disabled.'
        helpers.set_maintenance(False)
        return is_failed

    for upd in to_apply:
        is_failed = upd
        db_upd, upgrade_func, downgrade_func, upgrade_node_func,\
            downgrade_node_func = load_update(upd)
        if not db_upd:
            break

        if upgrade_master(upgrade_func, downgrade_func, db_upd,
                          with_testing):
            if upgrade_node_func:
                if upgrade_nodes(upgrade_node_func, downgrade_node_func,
                                 db_upd, with_testing):
                    is_failed = False
                    db_upd.status = UPDATE_STATUSES.applied
                    try:
                        db_upd.print_log('{0} successfully applied. '
                                     'All nodes are upgraded'.format(upd))
                    except sqlalchemy.orm.exc.DetachedInstanceError:
                        new_db_upd = Updates.query.get(upd)
                        if new_db_upd:
                            new_db_upd.print_log('{0} successfully applied'.format(upd))
                else:   # not successful
                    db_upd.status = UPDATE_STATUSES.nodes_failed
                    db_upd.print_log("{0} failed. Unable to upgrade some nodes"
                                     .format(upd))
            else:
                is_failed = False
                db_upd.status = UPDATE_STATUSES.applied
                try:
                    db_upd.print_log('{0} successfully applied'.format(upd))
                except sqlalchemy.orm.exc.DetachedInstanceError:
                    new_db_upd = Updates.query.get(upd)
                    if new_db_upd:
                        new_db_upd.print_log('{0} successfully applied'.format(upd))
        db_upd.end_time = datetime.utcnow()
        db.session.commit()
    if is_failed:
        print >> sys.stderr, "Update {0} has failed.".format(is_failed)
        sys.exit(2)
    else:
        helpers.restart_service(settings.KUBERDOCK_SERVICE)
        helpers.set_maintenance(False)
        print 'All update scripts are applied. Kuberdock has been restarted. ' \
              'Maintenance mode is now disabled.'
    return is_failed


def get_kuberdocks_toinstall(testing=False):
    """
    :param testing: boolean to enable testing repo during check
    :return: sorted list of kuberdock packages that newer then installed one.
    """
    yb = yum.YumBase()
    yb.conf.cache = 0
    yb.repos.enableRepo('kube')
    if testing:
        yb.repos.enableRepo('kube-testing')
    yb.cleanMetadata()  # only after enabling repos to clean them too!

    try:
        installed_kuberdock = list(
            yb.doPackageLists('installed', patterns=['kuberdock']))[0]
    except IndexError:
        print >> sys.stderr, 'Kuberdock package is not installed'
        sys.exit(1)

    try:
        all_kuberdocks = yb.doPackageLists(pkgnarrow='available',
                                           showdups=True,
                                           patterns=['kuberdock'])
    except yum.Errors.YumBaseError:
        all_kuberdocks = []

    l = sorted([i for i in all_kuberdocks if i > installed_kuberdock])
    return [i.nvra for i in l]  # extra step for proper sorting


def parse_cmdline():
    root_parser = argparse.ArgumentParser(
        description='Kuberdock update management utility. '
                    'Should be run from root.')

    root_parser.add_argument('-t', '--use-testing',
                             action='store_true',
                             help='Enable testing repo during upgrade')
    root_parser.add_argument(
        '--local',
        help='Filename of local package to install for upgrade')
    root_parser.add_argument(
        '-r', '--reinstall',
        action='store_true',
        help='Try "reinstall" instead of "install" for upgrading package')

    subparsers = root_parser.add_subparsers(dest='command', help='Commands')

    upgrade_cmd = subparsers.add_parser(
        CLI_COMMANDS.upgrade,
        help='Upgrade Kuberdock. '
             'Default command, no need to specify explicitly')

    resume_upgrade_cmd = subparsers.add_parser(
        CLI_COMMANDS.resume_upgrade,
        help='Tries to restart failed upgrade scripts. '
             'Useful if you fix all problems manually, but in common case '
             'failed update scripts will be restarted during update to new '
             'package release from repo via "{0}" command'
             .format(CLI_COMMANDS.upgrade))

    maintenance_cmd = subparsers.add_parser(
        CLI_COMMANDS.set_maintenance,
        help='Used to manually enable or disable cluster maintenance mode')
    maintenance_cmd.add_argument(
        dest='maintenance',
        choices=('on', '1', 'off', '0'),
        help='Boolean state of cluster maintenance mode')

    node_schedulable_cmd = subparsers.add_parser(
        CLI_COMMANDS.set_node_schedulable,
        help='Used to manually set node schedulable mode')
    node_schedulable_cmd.add_argument(
        dest='schedulable',
        choices=('on', '1', 'off', '0'),
        help='Boolean state of node schedulable mode')
    node_schedulable_cmd.add_argument(
        dest='node',
        help='Node hostname')

    # for default subparser
    if filter(lambda x: not x.startswith('__') and x in CLI_COMMANDS.__dict__.values(), sys.argv[1:]):
        return root_parser.parse_args()
    else:
        return root_parser.parse_args(sys.argv[1:] + [CLI_COMMANDS.upgrade])


def setup_fabric():
    env.user = 'root'
    env.abort_exception = helpers.UpgradeError
    env.key_filename = settings.SSH_KEY_FILENAME
    env.warn_only = True
    output.stdout = False
    output.aborts = False


if __name__ == '__main__':

    if os.getuid() != 0:
        print 'Root permissions required to run this script'
        sys.exit()

    setup_fabric()

    AFTER_RELOAD = False
    if CLI_COMMANDS.after_reload in sys.argv:
        sys.argv.remove(CLI_COMMANDS.after_reload)
        AFTER_RELOAD = True
    args = parse_cmdline()

    if args.command == CLI_COMMANDS.set_maintenance:
        if args.maintenance in ('on', '1'):
            helpers.set_maintenance(True)
        else:
            helpers.set_maintenance(False)
        sys.exit(0)
    if args.command == CLI_COMMANDS.set_node_schedulable:
        if args.schedulable in ('on', '1'):
            set_schedulable(args.node, True)
        else:
            set_schedulable(args.node, False)
        sys.exit(0)

    app = create_app()
    directory = os.path.join(
        os.path.dirname(os.path.realpath(__file__)), 'kdmigrations')
    migrate = Migrate(app, db, directory)

    # All commands that need app context are follow here:
    with app.app_context():
        if AFTER_RELOAD:
            try:
                os.unlink(settings.UPDATES_RELOAD_LOCK_FILE)
            except OSError:
                pass
            do_cycle_updates(args.use_testing)
            if not args.local:
                print 'Restarting upgrade script to check next new package...'
                os.execv(__file__, sys.argv)
            sys.exit(0)     # if local install case
        if args.command == CLI_COMMANDS.resume_upgrade:
            helpers.set_maintenance(True)
            do_cycle_updates(args.use_testing)
            sys.exit(0)
        if args.command == CLI_COMMANDS.upgrade:
            if args.use_testing:
                print 'Testing repo enabled.'
            if args.local:
                # Check if it's newer
                res = subprocess.call(['rpm', '-i', '--replacefiles',
                                       '--nodeps',
                                       '--test',
                                       args.local])
                new_kuberdocks = [] if res and not args.reinstall else [args.local]
            else:
                new_kuberdocks = get_kuberdocks_toinstall(args.use_testing)
            if new_kuberdocks:
                if not args.reinstall:
                    print 'Newer kuberdock package is available.'
                ans = raw_input('Do you want to upgrade it ? [y/n]:')
                if ans in ('y', 'yes'):
                    helpers.set_maintenance(True)
                    # use new_kuberdocks[0] instead because of execv:
                    for pkg in new_kuberdocks:
                        err = helpers.install_package(pkg, args.use_testing,
                                                      args.reinstall)
                        if err:
                            print >> sys.stderr,\
                                "Update package to {0} has failed.".format(pkg)
                            print >> sys.stderr, FAILED_MESSAGE
                            sys.exit(err)
                        # Now, after successfully upgraded package:
                        open(settings.UPDATES_RELOAD_LOCK_FILE, 'a').close()
                        print 'Restarting this script from new package...'
                        os.execv(__file__,
                                 sys.argv + [CLI_COMMANDS.after_reload])
                else:
                    print 'Stop upgrading.'
                    sys.exit(0)
            else:
                print 'Kuberdock is up to date.'

#!/usr/bin/env python

import os
import re
import yum
import sys
import json
import argparse
import itertools
import subprocess
import requests

from datetime import datetime
from importlib import import_module
from fabric.api import env, run
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
from kubedock.core import ConnectionPool
from kubedock.updates.health_check import check_cluster


class CLI_COMMANDS:
    upgrade = 'upgrade'
    resume_upgrade = 'resume-upgrade'
    set_maintenance = 'set-maintenance'
    set_node_schedulable = 'set-node-schedulable'
    # not documented for user. It's for internal use only:
    after_reload = '--after-reload'
    apply_one = 'apply-one'
    concat_updates = 'concat-updates'
    health_check_only = 'health-check-only'


FAILED_MESSAGE = """\
Cluster was left in a maintenance mode, please contact to support team for help.
Use {0} {1} on|off to manually switch cluster work mode (careful!)\
""".format(os.path.basename(__file__), CLI_COMMANDS.set_maintenance)


SUCCESSFUL_DOWNGRADE_MESSAGE = """\
Downgrade looks successful but please ensure that all works properly.
Kuberdock has been restarted.\
""".format(os.path.basename(__file__), CLI_COMMANDS.set_maintenance)


SUCCESSFUL_UPDATE_MESSAGE = """
********************
Kuberdock has been restarted.
Maintenance mode is now disabled.
********************
"""


def get_available_updates():
    patt = re.compile(r'^[0-9]{5}_update\.py$')
    return sorted(filter(patt.match, os.listdir(settings.UPDATES_PATH)))


def get_applied_updates():
    return sorted(
        [i.fname for i in Updates.query.filter_by(
            status=UPDATE_STATUSES.applied).all()])

# TODO Add get_next_update, may be generator


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
        except (requests.RequestException, ValueError, KeyError):
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
    except Exception as e:
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
    successful = True
    if db_upd.status == UPDATE_STATUSES.nodes_failed:
        nodes = db.session.query(Node).filter(
            or_(Node.upgrade_status == UPDATE_STATUSES.failed,
                Node.upgrade_status == UPDATE_STATUSES.failed_downgrade)).all()
    else:
        nodes = db.session.query(Node).all()

    db_upd.status = UPDATE_STATUSES.nodes_started
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
            run('yum --enablerepo=kube,kube-testing clean metadata')
            upgrade_node(db_upd, with_testing, env)
        except Exception as e:
            successful = False
            node.upgrade_status = UPDATE_STATUSES.failed
            db_upd.capture_traceback(
                'Exception raised during '
                'upgrade node {0}'.format(node.hostname)
            )
            try:
                downgrade_node(db_upd, with_testing, env, e)
            except Exception as e:
                node.upgrade_status = UPDATE_STATUSES.failed_downgrade
                db_upd.capture_traceback(
                    'Exception raised during '
                    'downgrade node {0}'.format(node.hostname)
                )
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
        db.session.rollback()
        db_upd.status = UPDATE_STATUSES.failed
        db_upd.capture_traceback(
            'Error in update script {0}'.format(db_upd.fname),
            'Starting downgrade...'
        )
        try:
            downgrade_func(db_upd, with_testing, e)
        except Exception as e:
            db_upd.status = UPDATE_STATUSES.failed_downgrade
            db_upd.capture_traceback(
                'Error downgrading script {0}'.format(db_upd.fname)
            )
        else:   # TODO don't sure about restart in this case
            helpers.restart_service(settings.KUBERDOCK_SERVICE)
            db_upd.print_log(SUCCESSFUL_DOWNGRADE_MESSAGE)
        return False
    db_upd.status = UPDATE_STATUSES.master_applied
    return True


def run_script(upd, with_testing):
    """
    :param upd: update script file name
    :param with_testing: bool enable testing or not
    :return: True if successful else False
    """
    db_upd, upgrade_func, downgrade_func, upgrade_node_func,\
        downgrade_node_func = load_update(upd)
    if not db_upd:
        print >> sys.stderr, "Failed to load upgrade script file"
        return False

    master_ok = upgrade_master(upgrade_func, downgrade_func, db_upd,
                               with_testing)
    if master_ok:
        if upgrade_node_func:
            nodes_ok = upgrade_nodes(upgrade_node_func, downgrade_node_func,
                                     db_upd, with_testing)
            if nodes_ok:
                db_upd.status = UPDATE_STATUSES.applied
                db_upd.print_log('{0} successfully applied. '
                                 'All nodes are upgraded'.format(upd))
                res = True
            else:
                db_upd.status = UPDATE_STATUSES.nodes_failed
                db_upd.print_log("{0} failed. Unable to upgrade some nodes"
                                 .format(upd))
                res = False
        else:
            db_upd.status = UPDATE_STATUSES.applied
            db_upd.print_log('{0} successfully applied'.format(upd))
            res = True
    else:
        res = False
    db_upd.end_time = datetime.utcnow()
    db.session.commit()
    return res


def do_cycle_updates(with_testing=False):
    """
    :return: False if no errors or script name at which was error
    """
    # TODO refactor to 'get next update'
    to_apply = get_available_updates()
    last = get_applied_updates()
    if last:
        # Start from last failed update
        to_apply = to_apply[to_apply.index(last[-1]) + 1:]
    if not to_apply:
        helpers.restart_service(settings.KUBERDOCK_SERVICE)
        helpers.set_maintenance(False)
        print 'There is no new upgrade scripts to apply. ' + \
              SUCCESSFUL_UPDATE_MESSAGE
        return False

    is_failed = False
    for upd in to_apply:
        if not run_script(upd, with_testing):
            is_failed = upd
            print >> sys.stderr, "Update {0} has failed.".format(is_failed)
            break

    if not is_failed:
        helpers.close_all_sessions()
        print 'All update scripts are applied.'
    return is_failed


def prepare_repos(testing):
    yb = yum.YumBase()
    yb.conf.cache = 0
    yb.repos.enableRepo('kube')
    if testing:
        yb.repos.enableRepo('kube-testing')
    yb.cleanMetadata()  # only after enabling repos to clean them too!
    return yb


def ask_upgrade():
    ans = raw_input('Do you want to upgrade it ? [y/n]:')
    while ans not in ('y', 'yes', 'n', 'no',):
        print 'Only y/yes or n/no answers accepted, please try again'
        ans = raw_input('Do you want to upgrade it ? [y/n]:')
    return ans in ('y', 'yes')


def health_check():
    if not args.skip_health_check:
        print "Performing cluster health check..."
        msg = check_cluster()
        if msg:
            print >> sys.stderr, "There are some problems with cluster."
            print >> sys.stderr, msg
            print >> sys.stderr, "Please, solve problems or use key --skip-health-check.(on your own risk)"
            return False
        print "Health check: OK"
    else:
        print "Skipping health check."
    return True


def pre_upgrade():
    """
    Setup common things needed for upgrade. May be called multiple times
    :return: Error or True if any error else False
    """
    if not health_check():
        return True
    helpers.set_maintenance(True)
    if helpers.set_evicting_timeout('99m0s'):
        print >> sys.stderr, "Can't set pods evicting interval."
        print >> sys.stderr, "No new upgrades are applied. Exit."
        print >> sys.stderr, FAILED_MESSAGE
        return True     # means common error case
    return False


def post_upgrade(for_successful=True, reason=None):     # teardown
    """
    Teardown after upgrade
    :return: Error or True if any error else False
    """
    if helpers.set_evicting_timeout('5m0s'):
        print >> sys.stderr, "Can't bring back old pods evicting interval."
        for_successful = False
    if for_successful:
        helpers.restart_service(settings.KUBERDOCK_SERVICE)
        helpers.set_maintenance(False)
        redis = ConnectionPool.get_connection()
        redis.delete('KDCOLLECTION')
        print SUCCESSFUL_UPDATE_MESSAGE
    else:
        if reason is not None:
            print >> sys.stderr, reason
        print >> sys.stderr, FAILED_MESSAGE


def get_kuberdocks_toinstall(testing=False):
    """
    :param testing: boolean to enable testing repo during check
    :return: sorted list of kuberdock packages that newer then installed one.
    """
    yb = prepare_repos(testing)

    try:
        installed_kuberdock = list(
            yb.doPackageLists('installed', patterns=['kuberdock']))[0]

        all_kuberdocks = yb.doPackageLists(pkgnarrow='available',
                                           showdups=True,
                                           patterns=['kuberdock'])
    except IndexError:
        print >> sys.stderr, 'Kuberdock package is not installed'
        sys.exit(1)
    except yum.Errors.YumBaseError as e:
        print >> sys.stderr, 'Error while retrieving package list:'
        print >> sys.stderr, e
        sys.exit(1)

    # Don't use i.envra right here because sorting will be incorrect
    sorted_available = sorted([i for i in all_kuberdocks if i > installed_kuberdock])

    # For each KD version leave only packages with latest release number
    by_version = itertools.groupby(sorted_available, lambda x: x.version)
    return [max(ver[1]).envra for ver in by_version]


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
        '--skip-health-check',
        action='store_true',
        help='Skip health check of cluster')
    root_parser.add_argument(
        '-r', '--reinstall',
        action='store_true',
        help='Try "reinstall" instead of "install" for upgrading package')

    subparsers = root_parser.add_subparsers(dest='command', help='Commands')

    upgrade_cmd = subparsers.add_parser(
        CLI_COMMANDS.upgrade,
        help='Upgrade Kuberdock. '
             'Default command, no need to specify explicitly')

    health_check_only_cmd = subparsers.add_parser(
        CLI_COMMANDS.health_check_only,
        help='Perform cluster health check only, without upgrade')

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

    apply_one_cmd = subparsers.add_parser(
        CLI_COMMANDS.apply_one,
        help='Used to manually run specified upgrade script')
    apply_one_cmd.add_argument(
        dest='script_file',
        help='Update script file name (without path)')

    concat_updates_cmd = subparsers.add_parser(
        CLI_COMMANDS.concat_updates,
        help='Concat update to one file')
    concat_updates_cmd.add_argument(
        '--new_update',
        dest='new_update',
        nargs='?',
        help='Name of new update file (without path)')
    concat_updates_cmd.add_argument(
        '--first_update',
        dest='first_update',
        nargs='?',
        help='Name of first update file to concat (without path)')
    concat_updates_cmd.add_argument(
        '--last_update',
        dest='last_update',
        nargs='?',
        help='Name of last update file to concat (without path)')

    # for default subparser
    if filter(lambda x: not x.startswith('__') and x in CLI_COMMANDS.__dict__.values(), sys.argv[1:]):
        return root_parser.parse_args()
    else:
        return root_parser.parse_args(sys.argv[1:] + [CLI_COMMANDS.upgrade])


def concat_updates(first_update=None, last_update=None, new_update=None):
    updates = get_available_updates()
    if not first_update:
        first_update = get_applied_updates()[0]
    if not last_update:
        last_update = updates[-1]
    if not new_update:
        new_update = "%05d_update.py" % (int(updates[-1][:5]) + 1)
    new_update_file = os.path.join(settings.UPDATES_PATH, new_update)
    with open(new_update_file, 'w') as newf:
        sb = updates[updates.index(first_update):updates.index(last_update) + 1]
        for update in sb:
            update_file = os.path.join(settings.UPDATES_PATH, update)
            with open(update_file) as f:
                newf.write("# {update}{sep}".format(
                    update=update, sep=2 * os.linesep))
                newf.write(f.read())
            os.remove(update_file)
            print "remove: {}".format(update)
    print "create: {}".format(new_update_file)


if __name__ == '__main__':

    if os.getuid() != 0:
        print 'Root permissions required to run this script'
        sys.exit()

    helpers.setup_fabric()

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

            err = do_cycle_updates(args.use_testing)
            post_upgrade(for_successful=not err)
            if not args.local:
                print 'Restarting upgrade script to check next new package...'
                os.execv(__file__, sys.argv)
            sys.exit(0)     # if local install case

        if args.command == CLI_COMMANDS.resume_upgrade:
            if pre_upgrade():
                sys.exit(3)
            err = do_cycle_updates(args.use_testing)
            post_upgrade(for_successful=not err)
            sys.exit(0)

        if args.command == CLI_COMMANDS.apply_one:
            if not os.path.exists(os.path.join(settings.UPDATES_PATH,
                                               args.script_file)):
                print 'There is no such upgrade script in scripts directory'
                sys.exit(0)
            if pre_upgrade():
                sys.exit(3)
            ok = run_script(args.script_file, args.use_testing)
            post_upgrade(for_successful=ok)
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
                # To clean up repo cache:
                ybase = prepare_repos(args.use_testing)
                new_kuberdocks = [] if res and not args.reinstall else [args.local]
            else:
                new_kuberdocks = get_kuberdocks_toinstall(args.use_testing)
            if new_kuberdocks:
                pkg = new_kuberdocks[0]
                if not args.reinstall:
                    print 'Newer kuberdock package is available: {0}'.format(pkg)
                if ask_upgrade():
                    if pre_upgrade():
                        sys.exit(3)
                    err = helpers.install_package(pkg, args.use_testing,
                          action='reinstall' if args.reinstall else 'install')
                    if err:
                        post_upgrade(for_successful=False,
                                     reason="Update package to {0} has failed."
                                     .format(pkg))
                        sys.exit(err)
                    # Now, after successfully upgraded master package:
                    open(settings.UPDATES_RELOAD_LOCK_FILE, 'a').close()
                    print 'Restarting this script from new package...'
                    os.execv(__file__, sys.argv + [CLI_COMMANDS.after_reload])
                else:
                    print 'Stop upgrading.'
                    sys.exit(0)
            else:
                print 'Kuberdock is up to date.'
        if args.command == CLI_COMMANDS.health_check_only:
            if not health_check():
                sys.exit(1)
            sys.exit(0)

        if args.command == CLI_COMMANDS.concat_updates:
            concat_updates(args.first_update, args.last_update, args.new_update)

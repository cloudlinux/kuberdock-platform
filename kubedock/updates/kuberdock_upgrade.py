#!/usr/bin/python

import os
import yum
import sys
import argparse
import subprocess
from datetime import datetime
from importlib import import_module

if __name__ == '__main__' and __package__ is None:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.realpath(__file__)))))

from kubedock.api import create_app
from kubedock.settings import KUBERDOCK_SERVICE
from kubedock.updates import helpers
from kubedock.updates.models import Updates, db
from flask.ext.migrate import Migrate

FAILED_MESSAGE = """\
Cluster was left in a maintenance mode, \
please contact to support team for help. \
Use kuberdock-upgrade.py --set-maintenance=true|false to manually switch \
cluster work mode(Careful!)
"""


def do_cycle_updates(with_testing=False):
    """
    :return: False if no errors or script name at which was error
    """
    to_apply = helpers.get_available_updates()
    last = helpers.get_applied_updates()
    if last:
        to_apply = to_apply[to_apply.index(last[-1])+1:]
    failed = False
    if not to_apply:
        print 'There is no new upgrade scripts to apply.'
        return failed

    for upd in to_apply:
        failed = upd
        in_db_update = Updates.query.get(upd) or \
                       Updates(fname=upd,
                               status=helpers.UPDATE_STATUSES.started,
                               start_time=datetime.utcnow())
        in_db_update.status = helpers.UPDATE_STATUSES.started
        db.session.add(in_db_update)
        db.session.commit()

        try:
            module = import_module('scripts.' + upd.rsplit('.py')[0])
        except ImportError as e:
            helpers.print_log(in_db_update,
                              'Error importing update script {0}. {1}'
                              .format(upd, e))
            in_db_update.status = helpers.UPDATE_STATUSES.failed
            db.session.commit()
            break
        try:
            module.upgrade(in_db_update, with_testing)
            helpers.print_log(in_db_update,
                              '{0} successfully applied'.format(upd))
        except Exception as e:
            failed = upd
            in_db_update.status = helpers.UPDATE_STATUSES.failed
            helpers.print_log(in_db_update,
                              'Error in update script '
                              '{0}. {1}. Starting downgrade...'
                              .format(upd, e.__repr__()))
            try:
                module.downgrade(in_db_update, with_testing)
            except Exception as e:
                in_db_update.status = helpers.UPDATE_STATUSES.failed_downgrade
                helpers.print_log(in_db_update,
                                  'Error downgrading script {0}. {1}'
                                  .format(upd, e))
                helpers.print_log(in_db_update, FAILED_MESSAGE)
            else:
                helpers.restart_service(KUBERDOCK_SERVICE)  # TODO ?
                helpers.set_maintenance(False)
            break
        else:
            in_db_update.status = helpers.UPDATE_STATUSES.applied
            failed = False
        finally:
            in_db_update.end_time = datetime.utcnow()
            db.session.commit()
    if failed:
        print >> sys.stderr, "Update {0} has failed.".format(failed)
        sys.exit(2)
    else:
        print 'All update scripts are applied.'
        helpers.set_maintenance(False)
        helpers.restart_service(KUBERDOCK_SERVICE)
    return failed


if __name__ == '__main__':

    parser = argparse.ArgumentParser(
        description='Kuberdock update management utility.')
    parser.add_argument('-t', '--use-testing',
                        action='store_true',
                        help='Enable testing repo during update')
    parser.add_argument('--set-maintenance',
                        choices=('true', 'on', '1', 'false', 'off', '0'),
                        nargs='?',
                        help='Used to manually enable or disable cluster '
                             'maintenance mode')
    args = parser.parse_args()

    if args.set_maintenance:
        if args.set_maintenance in ('true', 'on', '1'):
            helpers.set_maintenance(True)
        else:
            helpers.set_maintenance(False)
        sys.exit(0)

    yb = yum.YumBase()
    yb.conf.cache = 0
    yb.cleanMetadata()

    if args.use_testing:
        yb.repos.enableRepo('kube-testing')
        print 'Testing repo enabled.'

    app = create_app()
    directory = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                             'kdmigrations')
    migrate = Migrate(app, db, directory)

    with app.app_context():
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

        new_kuberdocks = sorted(
            [i for i in all_kuberdocks if i > installed_kuberdock])

        if new_kuberdocks:
            print 'Newer kuberdock package is available.'
            ans = raw_input('Do you want to upgrade it ? [y/n]:')
            if ans in ('y', 'yes'):
                helpers.set_maintenance(True)
                # use new_kuberdocks[0] instead because of execv:
                for pkg in new_kuberdocks:
                    opts = ['yum', '--enablerepo=kube',
                            '-y',
                            'install', pkg.nvra]
                    if args.use_testing:
                        opts[1] += ',kube-testing'
                    err = subprocess.call(opts)
                    if err:
                        print >> sys.stderr,\
                            "Update package to {0} has failed.".format(pkg.nvra)
                        print >> sys.stderr, FAILED_MESSAGE
                        sys.exit(err)
                    do_cycle_updates(args.use_testing)
                    print 'Restarting upgrade script from new package...'
                    os.execv(__file__, sys.argv)
            else:
                print 'Stop upgrading.'
                sys.exit(0)
        else:
            print 'Kuberdock is up to date.'

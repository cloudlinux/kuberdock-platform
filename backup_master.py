#!/usr/bin/env python
# -*- coding: utf-8 -*-

import abc
import time
import argparse
import datetime
import grp
import logging
import os
import pwd
import shutil
import subprocess
import sys
import tempfile
import zipfile

logger = logging.getLogger("kd_master_backup")
logger.setLevel(logging.INFO)

stdout_handler = logging.StreamHandler()
logger.addHandler(stdout_handler)

formatter = logging.Formatter(
    "[%(asctime)-15s - %(name)-6s - %(levelname)-8s]"
    " %(message)s")
stdout_handler.setFormatter(formatter)


DATABASES = ('kuberdock', )
NICENESS = 19
ETCD_DATA = '/var/lib/etcd/default.etcd/member/'
KNOWN_TOKENS = '/etc/kubernetes/known_tokens.csv'
NODE_CONFIGFILE = '/etc/kubernetes/configfile_for_nodes'
SSH_KEY = '/var/lib/nginx/.ssh/id_rsa'
ETCD_PKI = '/etc/pki/etcd/'
LICENSE = '/var/opt/kuberdock/.license'
CEPH_SETTINGS = '/var/opt/kuberdock/kubedock/ceph_settings.py'
CEPH_CONFIG = '/var/lib/kuberdock/conf'
LOCKFILE = '/var/lock/kd-master-backup.lock'


def lock(lockfile):
    def decorator(clbl):
        def wrapper(*args, **kwargs):
            try:
                # Create or fail
                os.open(lockfile, os.O_CREAT | os.O_EXCL)
            except OSError:
                raise BackupError(
                    "Another backup/restore process already running."
                    " If it is not, try to remove `{0}` and "
                    "try again.".format(lockfile))
            try:
                result = clbl(*args, **kwargs)
            finally:
                os.unlink(lockfile)
            return result

        return wrapper

    return decorator


class BackupError(Exception):
    pass


def nice(cmd, n):
    return ["nice", "-n", str(n), ] + cmd


def sudo(cmd, as_user):
    return ["sudo", "-Hiu", as_user] + cmd


def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for fn in files:
            full_fn = os.path.join(root, fn)
            ziph.write(full_fn, os.path.relpath(full_fn, path))


def rmtree(path):
    # Workaround for https://github.com/hashdist/hashdist/issues/113
    cmd = ["rm", "-rf", path]
    subprocess.call(cmd)


def pg_dump(src, dst, db_username="postgres"):
    cmd = sudo(nice(["pg_dump", "-C", "-Fc", "-U",
                     db_username, src], NICENESS), "postgres")
    with open(dst, 'wb') as out:
        subprocess.check_call(cmd, stdout=out)


def etcd_backup(src, dst):
    cmd = nice(["etcdctl", "backup", "--data-dir", src, "--backup-dir", dst],
               NICENESS)
    subprocess.check_call(cmd, stdout=subprocess.PIPE)


def pg_restore(src, db_username="postgres"):
    cmd = sudo(["psql", "-c", "DROP DATABASE {}".format(DATABASES[0])],
               "postgres")
    subprocess.check_call(cmd)

    cmd = sudo(["psql", "-c", "CREATE DATABASE {} ENCODING 'UTF8'".format(
        DATABASES[0])], "postgres")
    subprocess.check_call(cmd)

    cmd = sudo(["pg_restore", "-U", db_username, "-n", "public",
                "-1", "-d", "kuberdock", src],
               "postgres")
    subprocess.check_call(cmd)


def etcd_restore(src, dst):
    cmd = ["etcdctl", "backup", "--data-dir", src, "--backup-dir", dst]
    subprocess.check_call(cmd, stdout=subprocess.PIPE)


def delete_nodes():
    """ Delete all nodes from restored cluster.

    When restoring cluster after a full crush it makes sense to drop nodes
    from restored db because they will be added again (re-deployed). This also
    implies purging of the pods - in this case they also need to be re-deployed
    (or restored from pod backups)
    """

    from kubedock.core import db
    from kubedock.api import create_app
    from kubedock.pods.models import PersistentDisk, Pod, PodIP
    from kubedock.usage.models import IpState, ContainerState, PodState
    from kubedock.domains.models import PodDomain
    from kubedock.nodes.models import Node
    from kubedock.kapi.nodes import delete_node_from_db

    create_app(fake_sessions=True).app_context().push()
    IpState.query.delete()
    PodIP.query.delete()
    ContainerState.query.delete()
    PodDomain.query.delete()
    PersistentDisk.query.delete()
    PodState.query.delete()
    Pod.query.delete()
    logger.info("All pod data purged.")
    db.session.commit()

    devnull = open(os.devnull, 'w')
    subprocess.call(['kubectl', 'delete', '--all', 'namespaces'],
                    stderr=devnull, stdout=devnull)
    subprocess.call(['kubectl', 'delete', '--all', 'nodes'],
                    stderr=devnull, stdout=devnull)
    logger.info("Etcd data purged.")

    for node in Node.get_all():
        delete_node_from_db(node)
        logger.info("Node `{0}` purged.".format(node.hostname))


class BackupResource(object):

    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def backup(cls, dst):
        pass

    @abc.abstractmethod
    def restore(cls, zip_archive, **kwargs):
        pass


class PostgresResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        _, postgres_tmp = tempfile.mkstemp(prefix="postgres-", dir=dst,
                                           suffix='.backup.in_progress')
        pg_dump(DATABASES[0], postgres_tmp)

        result = os.path.join(dst, "postgresql.backup")
        os.rename(postgres_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        fd, path = tempfile.mkstemp()
        try:
            uid = pwd.getpwnam("postgres").pw_uid
            os.fchown(fd, uid, -1)
            with os.fdopen(fd, 'w') as tmp:
                shutil.copyfileobj(zip_archive.open('postgresql.backup'), tmp)
                tmp.seek(0)
                pg_restore(path)
        finally:
            os.remove(path)
        return path


class EtcdCertResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        pki_src = '/etc/pki/etcd/'
        etcd_tmp = tempfile.mkdtemp(prefix="etcd-pki-", dir=dst,
                                    suffix="-inprogress")
        for fn in os.listdir(pki_src):
            shutil.copy(os.path.join(pki_src, fn), etcd_tmp)

        result = os.path.join(dst, "etcd_pki")
        os.rename(etcd_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        src = tempfile.mkdtemp()
        zip_archive.extractall(src, zip_archive.namelist())
        pki_src = os.path.join(src, 'etcd_pki')
        try:
            for fn in os.listdir(pki_src):
                shutil.copy(os.path.join(pki_src, fn), ETCD_PKI)
        finally:
            rmtree(src)
        return ETCD_PKI


class EtcdDataResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        etcd_tmp = tempfile.mkdtemp(prefix="etcd-", dir=dst,
                                    suffix="-inprogress")

        for fn in os.listdir(ETCD_DATA):
            copy_from = os.path.join(ETCD_DATA, fn)
            copy_to = os.path.join(etcd_tmp, fn)
            shutil.copytree(copy_from, copy_to)

        open(os.path.join(etcd_tmp, 'snap', 'dummy'), 'a').close()
        result = os.path.join(dst, "etcd")
        os.rename(etcd_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        src = tempfile.mkdtemp()
        try:
            zip_archive.extractall(src, zip_archive.namelist())
            data_src = os.path.join(src, 'etcd')
            try:
                rmtree(os.path.join(ETCD_DATA, 'wal'))
                rmtree(os.path.join(ETCD_DATA, 'snap'))
            except OSError:
                pass

            for fn in os.listdir(data_src):
                copy_from = os.path.join(data_src, fn)
                copy_to = os.path.join(ETCD_DATA, fn)
                shutil.copytree(copy_from, copy_to)

            uid = pwd.getpwnam("etcd").pw_uid
            gid = grp.getgrnam("etcd").gr_gid
            for root, dirs, files in os.walk(ETCD_DATA):
                for fn in dirs:
                    os.chown(os.path.join(root, fn), uid, gid)
                for fn in files:
                    os.chown(os.path.join(root, fn), uid, gid)
        finally:
            rmtree(src)
        return src


class KubeConfigResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        try:
            from kubedock import ceph_settings
        except ImportError:
            return

        shutil.copy(CEPH_SETTINGS, dst)
        conf_tmp = tempfile.mkdtemp(prefix="ceph-", dir=dst,
                                    suffix="-inprogress")

        for fn in os.listdir(CEPH_CONFIG):
            copy_from = os.path.join(CEPH_CONFIG, fn)
            copy_to = os.path.join(conf_tmp, fn)
            shutil.copy(copy_from, copy_to)

        result = os.path.join(dst, "conf")
        os.rename(conf_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive):
        src = tempfile.mkdtemp()
        file_to_extract = filter(lambda x: x.startswith('conf/'),
                                 zip_archive.namelist())
        print(file_to_extract)
        if file_to_extract:
            zip_archive.extractall(src, file_to_extract)
            pki_src = os.path.join(src, 'conf')
            for fn in os.listdir(pki_src):
                shutil.copy(os.path.join(pki_src, fn), CEPH_CONFIG)

            with open(CEPH_SETTINGS, 'w') as tmp:
                with zip_archive.open('ceph_settings.py') as zip_file:
                    shutil.copyfileobj(zip_file, tmp)


class KubeTokenResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        shutil.copy(KNOWN_TOKENS, dst)
        shutil.copy(NODE_CONFIGFILE, dst)
        return ', '.join([os.path.join(dst, os.path.basename(x)) for x in [
            KNOWN_TOKENS,
            NODE_CONFIGFILE,
        ]])

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        with open(KNOWN_TOKENS, 'w') as tmp:
            shutil.copyfileobj(zip_archive.open('known_tokens.csv'), tmp)

        with open(NODE_CONFIGFILE, 'w') as tmp:
            shutil.copyfileobj(zip_archive.open('configfile_for_nodes'), tmp)


class SSHKeysResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        fd, key_tmp = tempfile.mkstemp(prefix="ssh-key-", dir=dst,
                                       suffix='.backup.in_progress')
        with open(SSH_KEY, 'r') as src:
            with os.fdopen(fd, 'w') as tmp_dst:
                shutil.copyfileobj(src, tmp_dst)

        shutil.copy(SSH_KEY + '.pub', dst)
        result = os.path.join(dst, "id_rsa")
        os.rename(key_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        with open(SSH_KEY, 'w') as keyfile:
            shutil.copyfileobj(zip_archive.open('id_rsa'), keyfile)
        with open(SSH_KEY + '.pub', 'w') as keyfile:
            shutil.copyfileobj(zip_archive.open('id_rsa.pub'), keyfile)
        return SSH_KEY


class LicenseResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        if os.path.isfile(LICENSE):
            shutil.copy(LICENSE, dst)
            return os.path.join(dst, '.license')

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        if '.license' in zip_archive.namelist():
            with open(LICENSE, 'w') as licfile:
                shutil.copyfileobj(zip_archive.open('.license'), licfile)
                return LICENSE


class SharedNginxConfigResource(BackupResource):

    config_src = '/etc/nginx/conf.d/'

    @classmethod
    def backup(cls, dst):
        config_tmp = tempfile.mkdtemp(prefix="nginx-config-", dir=dst,
                                      suffix="-inprogress")
        for fn in os.listdir(cls.config_src):
            shutil.copy(os.path.join(cls.config_src, fn), config_tmp)

        result = os.path.join(dst, "nginx_config")
        os.rename(config_tmp, result)
        return result

    @classmethod
    def restore(cls, zip_archive, **kwargs):
        src = tempfile.mkdtemp()
        try:
            zip_archive.extractall(src, filter(lambda x: x.startswith('nginx'),
                                               zip_archive.namelist()))
            pki_src = os.path.join(src, 'nginx_config')
            for fn in os.listdir(pki_src):
                shutil.copy(os.path.join(pki_src, fn), cls.config_src)
        finally:
            rmtree(src)
        return cls.config_src + "*"


backup_chain = [PostgresResource, EtcdDataResource, SSHKeysResource,
                EtcdCertResource, KubeTokenResource, LicenseResource,
                SharedNginxConfigResource, KubeConfigResource]

restore_chain = [PostgresResource, EtcdDataResource, SSHKeysResource,
                 EtcdCertResource, KubeTokenResource, LicenseResource,
                 SharedNginxConfigResource, KubeConfigResource]


@lock(LOCKFILE)
def do_backup(backup_dir, callback, skip_errors, **kwargs):

    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.datetime.today().isoformat()
    logger.info('Backup started {0}'.format(backup_dir))
    backup_dst = tempfile.mkdtemp(dir=backup_dir, prefix=timestamp)

    logger.addHandler(logging.FileHandler(os.path.join(backup_dst,
                      'main.log')))

    for res in backup_chain:
        try:
            logger.debug("Starting backup of {} resource".format(res.__name__))
            subresult = res.backup(backup_dst)
            if subresult:
                logger.info("File(s) collected: {0}".format(subresult))
        except subprocess.CalledProcessError as err:
            logger.error("%s backup error: %s" % (res, err))
            if not skip_errors:
                raise

    result = os.path.join(backup_dir, timestamp + ".zip")
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir(backup_dst, zipf)
    rmtree(backup_dst)

    logger.info('Backup finished successfully: {0}'.format(result))
    if callback:
        subprocess.Popen("{0} {1}".format(callback, result),
                         shell=True)
    return result


@lock(LOCKFILE)
def do_restore(backup_file, drop_nodes, skip_errors, **kwargs):
    """ Restore from backup file.
    If skip_error is True it will not interrupt restore due to errors
    raised on some step from restore_chain.
    If without_nodes is True it will remove any traces of old nodes
    right after restore is succeded.
    """
    logger.info('Restore started {0}'.format(backup_file))

    # Stop the app first, restart DB to make sure it does not have connections.
    subprocess.check_call(["systemctl", "stop", "emperor.uwsgi"])
    subprocess.check_call(["systemctl", "stop", "nginx"])
    subprocess.check_call(["systemctl", "restart", "postgresql"])

    if drop_nodes:
        restore_chain.remove(EtcdDataResource)

    with zipfile.ZipFile(backup_file, 'r') as zip_archive:
        for res in restore_chain:
            try:
                subresult = res.restore(zip_archive)
                if subresult:
                    logger.info("File restored: {0} ({1})".format(
                        subresult, res.__name__))
            except subprocess.CalledProcessError as err:
                logger.error("%s restore error: %s" % (res, err))
                if not skip_errors:
                    raise

    if drop_nodes:
        # etcd & k8s must be alive here
        delete_nodes()

    subprocess.check_call(["systemctl", "restart", "etcd"])
    time.sleep(5)
    subprocess.check_call(["systemctl", "restart", "kube-apiserver"])
    subprocess.check_call(["systemctl", "start", "nginx"])
    subprocess.check_call(["systemctl", "start", "emperor.uwsgi"])

    logger.info('Restore finished successfully.')


def parse_args(args):
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--verbose', help='Verbose (debug) logging',
                       action='store_const', const=logging.DEBUG,
                       dest='loglevel')
    group.add_argument('-q', '--quiet', help='Silent mode, only log warnings',
                       action='store_const', const=logging.WARN,
                       dest='loglevel')
    parser.add_argument("-s", '--skip-errors', action='store_true',
                        dest='skip_errors',
                        help="Do not stop if one of the steps is failed.")

    subparsers = parser.add_subparsers()

    parser_backup = subparsers.add_parser('backup', help='backup')
    parser_backup.add_argument('backup_dir',
                               help="Destination for all created files")
    parser_backup.add_argument(
        "-e", '--callback', help='Callback for each backup file'
        ' (backup path passed as a 1st arg)')
    parser_backup.set_defaults(func=do_backup)

    parser_restore = subparsers.add_parser('restore', help='restore')
    parser_restore.add_argument(
        "-d", '--drop-nodes', action='store_true', dest='drop_nodes',
        help="Drop nodes which exist in DB dump (choose this "
             "if you are going to re-deploy nodes thereafter)."
             " Note that this option also implies removing "
             "all user pods from the DB dump.")
    parser_restore.add_argument('backup_file')
    parser_restore.set_defaults(func=do_restore)

    return parser.parse_args(args)


def main():
    if os.getuid() != 0:
        raise Exception('Root permissions required to run this script')

    args = parse_args(sys.argv[1:])
    logger.setLevel(args.loglevel or logging.INFO)
    args.func(**vars(args))


if __name__ == '__main__':
    main()

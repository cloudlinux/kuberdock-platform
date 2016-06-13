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
SSH_KEY = '/var/lib/nginx/.ssh/id_rsa'
ETCD_PKI = '/etc/pki/etcd/'
LICENSE='/var/opt/kuberdock/.license'


class BackupError(Exception):
    pass


def nice(cmd, n):
    return ["nice", "-n", str(n), ] + cmd


def sudo(cmd, as_user):
    return ["sudo", "-u", as_user] + cmd


def zipdir(path, ziph):
    for root, dirs, files in os.walk(path):
        for fn in files:
            full_fn = os.path.join(root, fn)
            ziph.write(full_fn, os.path.relpath(full_fn, path))


def pg_dump(src, dst, username="postgres"):
    cmd = sudo(nice(["pg_dump", "-C", "-Fc", "-U",
                     username, src], NICENESS), "postgres")
    with open(dst, 'wb') as out:
        subprocess.check_call(cmd, stdout=out)


def etcd_backup(src, dst):
    cmd = nice(["etcdctl", "backup", "--data-dir", src, "--backup-dir", dst],
               NICENESS)
    subprocess.check_call(cmd, stdout=subprocess.PIPE)


class BackupResource(object):
    __metaclass__ = abc.ABCMeta

    @abc.abstractmethod
    def backup(cls, dst):
        pass

    @abc.abstractmethod
    def restore(cls, zf):
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
    def restore(cls, zf):
        fd, src = tempfile.mkstemp()
        try:
            uid = pwd.getpwnam("postgres").pw_uid
            os.fchown(fd, uid, -1)
            with os.fdopen(fd, 'w') as tmp:
                shutil.copyfileobj(zf.open('postgresql.backup'), tmp)
                tmp.seek(0)
                pg_restore(src)
        finally:
            os.remove(src)
        return src


class EtcdResource(BackupResource):

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
    def restore(cls, zf):
        src = tempfile.mkdtemp()
        try:
            zf.extractall(src, filter(lambda x: x.startswith('etcd'),
                          zf.namelist()))

            pki_src = os.path.join(src, 'etcd_pki')
            for fn in os.listdir(pki_src):
                shutil.copy(os.path.join(pki_src, fn), ETCD_PKI)

            data_src = os.path.join(src, 'etcd')
            try:
                shutil.rmtree(os.path.join(ETCD_DATA, 'wal'))
                shutil.rmtree(os.path.join(ETCD_DATA, 'snap'))
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
            shutil.rmtree(src)
        return src


class KubeTokenResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        shutil.copy(KNOWN_TOKENS, dst)
        return os.path.join(dst, 'known_tokens.csv')

    @classmethod
    def restore(cls, zf):
        with open(KNOWN_TOKENS, 'w') as tmp:
            shutil.copyfileobj(zf.open('known_tokens.csv'), tmp)


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
    def restore(cls, zf):
        with open(SSH_KEY, 'w') as tmp:
            shutil.copyfileobj(zf.open('id_rsa'), tmp)
        with open(SSH_KEY + '.pub', 'w') as tmp:
            shutil.copyfileobj(zf.open('id_rsa.pub'), tmp)
        return tmp


class EtcdCertResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        pki_src = '/etc/pki/etcd/'
        etcd_tmp = tempfile.mkdtemp(prefix="etcd-", dir=dst,
                                    suffix="-inprogress")
        for fn in os.listdir(pki_src):
            shutil.copy(os.path.join(pki_src, fn), etcd_tmp)

        result = os.path.join(dst, "etcd_pki")
        os.rename(etcd_tmp, result)
        return result

    @classmethod
    def restore(cls, zf):
        pass


class LicenseResource(BackupResource):

    @classmethod
    def backup(cls, dst):
        if os.path.isfile(LICENSE):
            shutil.copy(LICENSE, dst)
            return os.path.join(dst, '.license')

    @classmethod
    def restore(cls, zf):
        if '.license' in zf.namelist():
            with open(LICENSE, 'w') as tmp:
                shutil.copyfileobj(zf.open('.license'), tmp)


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
    def restore(cls, zf):
        src = tempfile.mkdtemp()
        try:
            zf.extractall(src, filter(lambda x: x.startswith('nginx'),
                          zf.namelist()))
            pki_src = os.path.join(src, 'nginx_config')
            for fn in os.listdir(pki_src):
                shutil.copy(os.path.join(pki_src, fn), cls.config_src)
        finally:
            shutil.rmtree(src)
        return src


backup_chain = (PostgresResource, EtcdResource, SSHKeysResource,
                EtcdCertResource, KubeTokenResource, LicenseResource,
                SharedNginxConfigResource)

restore_chain = (PostgresResource, EtcdResource, SSHKeysResource,
                 EtcdCertResource, KubeTokenResource, LicenseResource,
                 SharedNginxConfigResource)


def do_backup(backup_dir, callback, skip_errors, **kwargs):
    timestamp = datetime.datetime.today().isoformat()
    logger.info('Backup started {0}'.format(backup_dir))
    backup_dst = tempfile.mkdtemp(dir=backup_dir, prefix=timestamp)

    logger.addHandler(logging.FileHandler(os.path.join(backup_dst,
                      'main.log')))

    for res in backup_chain:
        try:
            subresult = res.backup(backup_dst)
            logger.info("File collected: {0}".format(subresult))
        except subprocess.CalledProcessError as err:
            logger.error("%s backuping error: %s" % (res, err))
            if not skip_errors:
                raise

    result = os.path.join(backup_dir, timestamp+".zip")
    with zipfile.ZipFile(result, 'w', zipfile.ZIP_DEFLATED) as zipf:
        zipdir(backup_dst, zipf)

    logger.info('Backup finished {0}'.format(result))
    if callback:
        subprocess.Popen("{0} {1}".format(callback, result),
                         shell=True)
    return result


def pg_restore(src, username="postgres"):
    cmd = sudo(["pg_restore", "-U", username, "-n", "public",
                "-c", "-1", "-d", "kuberdock", src], "postgres")
    subprocess.check_call(cmd)


def etcd_restore(src, dst):
    cmd = ["etcdctl", "backup", "--data-dir", src, "--backup-dir", dst]
    subprocess.check_call(cmd, stdout=subprocess.PIPE)


def do_restore(backup_file, skip_errors, **kwargs):
    logger.info('Restore started {0}'.format(backup_file))

    subprocess.check_call(["systemctl", "restart", "postgresql"])
    subprocess.check_call(["systemctl", "stop", "etcd", "kube-apiserver"])
    with zipfile.ZipFile(backup_file, 'r') as zf:
        for res in restore_chain:
            try:
                subresult = res.restore(zf)
                logger.info("File restored: {0} ({1})".format(subresult, res))
            except subprocess.CalledProcessError as err:
                logger.error("%s restore error: %s" % (res, err))
                if not skip_errors:
                    raise
    subprocess.check_call(["systemctl", "start", "etcd"])
    time.sleep(5)
    subprocess.check_call(["systemctl", "start", "kube-apiserver"])
    subprocess.check_call(["systemctl", "restart", "nginx"])
    logger.info('Restore finished')


def parse_args(args):
    parser = argparse.ArgumentParser()

    group = parser.add_mutually_exclusive_group()
    group.add_argument('-v', '--verbose', help='Verbose (debug) logging',
                       action='store_const', const=logging.DEBUG,
                       dest='loglevel')
    group.add_argument('-q', '--quiet', help='Silent mode, only log warnings',
                       action='store_const', const=logging.WARN,
                       dest='loglevel')
    parser.add_argument("-s", '--skip', action='store_false',
                        dest='skip_errors',
                        help="Do not stop if one steps is failed")

    subparsers = parser.add_subparsers()

    parser_backup = subparsers.add_parser('backup', help='backup')
    parser_backup.add_argument('backup_dir',
                               help="Destination for all created files")
    parser_backup.add_argument("-e", '--callback',
                               help='Callback for each file')
    parser_backup.set_defaults(func=do_backup)

    parser_restore = subparsers.add_parser('restore', help='restore')
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

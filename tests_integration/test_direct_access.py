import logging
import pexpect
import time
import os
import hashlib

from contextlib import contextmanager
from shutil import rmtree
from colorama import Style, Fore

from tests_integration.lib.integration_test_utils import (
    retry, ssh_exec, get_ssh, get_rnd_string)
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.exceptions import FileTransferValidationFailed

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


@pipeline('ssh_feature')
def test_ssh_feature(cluster):
    pod = cluster.pods.create('nginx', 'ssh_test_nginx_pod', start=True,
                              wait_for_status='running')
    creds = pod.ssh_credentials
    users, hosts, password = creds['users'], creds['hosts'], creds['password']

    with get_ssh(hosts[0], users[0], password) as conn:
        _create_container_files(conn, cluster.temp_files)

    # ===== SFTP tests =====
    sftp_tests = [_test_sftp_get_file, _test_sftp_get_dir, _test_sftp_put_file]
    for f in sftp_tests:
        with provision_container_and_host_files(pod, cluster.temp_files):
            f(hosts[0], users[0], password, cluster.temp_files)

    # ==== SCP tests ====
    scp_tests = [_test_scp_put_file, _test_scp_put_files, _test_scp_put_dir,
                 _test_scp_get_file, _test_scp_get_files, _test_scp_get_dir]
    for f in scp_tests:
        with provision_container_and_host_files(pod, cluster.temp_files):
            f(hosts[0], users[0], password, cluster.temp_files)

    # ==== SSH tests ====
    # Test ssh to running pods
    ssh_to_running_pod_tests = [_test_ssh_commands, _test_ssh_bash,
                                _test_ssh_with_wrong_credentials]
    for f in ssh_to_running_pod_tests:
        f(hosts[0], users[0], password)
    # Test ssh to stopped pods
    pod.stop()
    pod.wait_for_status('stopped')
    _test_ssh_to_stopped_container(hosts[0], users[0], password)


@contextmanager
def provision_container_and_host_files(pod, temp_files):
    creds = pod.ssh_credentials
    users, hosts, password = creds['users'], creds['hosts'], creds['password']
    try:
        yield
    finally:
        # Delete copied files on remote and host
        # Delete files on remote
        with get_ssh(hosts[0], users[0], password) as conn:
            sftp = conn.open_sftp()
            # Try to delete destination directory
            try:
                _rmtree(sftp, temp_files['remote_dst_dir'])
            except IOError:
                # No directory, just pass
                pass
            # Try to delete destination files
            try:
                for f in temp_files['local_files']:
                    sftp.remove(os.path.join(temp_files['remote_dst_dir'], f))
            except IOError:
                # No destination files just pass
                pass
            # Try to delete destination file
            try:
                sftp.remove(temp_files['remote_dst_file'])
            except IOError:
                # No destination file
                pass

        # Delete destination file on host
        if os.path.exists(temp_files['local_dst_file']):
            os.unlink(temp_files['local_dst_file'])
        # Clean local destination directory
        if os.path.exists(temp_files['local_dst_dir']):
            for p in os.listdir(temp_files['local_dst_dir']):
                path = os.path.join(temp_files['local_dst_dir'], p)
                if os.path.isdir(path):
                    rmtree(path)
                elif os.path.exists(path):
                    os.unlink(path)


def _test_sftp_put_file(host, user, password, temp_files):
    """
    Test sftp put file.
    """
    local_path = temp_files['local_src_file']
    remote_path = temp_files['remote_dst_file']

    logger.debug('==== sftp put file ====')

    _sftp_communicate(local_path, remote_path, user, host, password,
                      command='put')
    retry(validate_transfer, local_path=local_path, remote_path=remote_path,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_sftp_get_file(host, user, password, temp_files):
    """
    Test sftp get file
    """
    remote_path = temp_files['remote_src_file']
    local_path = temp_files['local_dst_file']

    logger.debug('==== sftp get file ====')

    _sftp_communicate(remote_path, local_path, user, host, password,
                      command='get')
    retry(validate_transfer, local_path=local_path, remote_path=remote_path,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_sftp_get_dir(host, user, password, temp_files):
    """
    Test sftp get directory
    """
    remote_path = temp_files['remote_src_dir']
    local_path = temp_files['local_dst_dir']

    logger.debug('==== sftp get directory ====')

    _sftp_communicate(remote_path, local_path, user, host, password,
                      command='get')

    basename = os.path.basename(os.path.normpath(remote_path))
    local_path = os.path.join(local_path, basename)

    retry(validate_transfer, local_path=local_path, remote_path=remote_path,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_scp_put_file(host, user, password, temp_files):
    """
    Test scp copy a single file on remote:
        $ scp local_file user@remote:/dest/path
    """
    local_path = temp_files['local_src_file']
    remote_path = os.path.dirname(temp_files['remote_dst_file'])

    logger.debug('===== scp put single file =====')

    cmd = 'scp {} {}@{}:{}'.format(local_path, user, host, remote_path)

    basename = os.path.basename(os.path.normpath(local_path))
    remote_file = os.path.join(remote_path, basename)
    _run_scp_command(cmd, user, host, password)

    retry(validate_transfer, local_path=local_path, remote_path=remote_file,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_scp_put_files(host, user, password, temp_files):
    """
    Test scp copy several files to remote:
        $ scp local_file1 local_file2 local_file2 user@remote:/dest/path
    """
    remote_path = temp_files['remote_dst_dir']

    local_files = [os.path.join(temp_files['local_src_dir'], f)
                   for f in temp_files['local_files']]
    remote_files = [os.path.join(remote_path, os.path.basename(v))
                    for v in local_files]

    logger.debug('===== scp put multiple files =====')

    cmd = 'scp {} {}@{}:{}'.format(' '.join(local_files), user, host,
                                   remote_path)
    _run_scp_command(cmd, user, host, password)

    for local_path, remote_path in zip(local_files, remote_files):
        retry(validate_transfer, local_path=local_path,
              remote_path=remote_path, user=user, host=host,
              password=password, tries=3, interval=1)


def _test_scp_put_dir(host, user, password, temp_files):
    """
    Test scp copy a directory to remote:
        $ scp -r local_directory user@host:/dst/path
    """
    local_path = temp_files['local_src_dir']
    remote_path = temp_files['remote_dst_dir']

    logger.debug('===== scp put directory =====')

    cmd = 'scp -r {} {}@{}:{}'.format(local_path, user, host, remote_path)
    basename = os.path.basename(os.path.normpath(local_path))
    remote_dir = os.path.join(remote_path, basename)

    _run_scp_command(cmd, user, host, password)
    retry(validate_transfer, local_path=local_path, remote_path=remote_dir,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_scp_get_dir(host, user, password, temp_files):
    """
    Test scp copy directory from remote:
        $ scp -r user@remote:path/to/src/dir dst/path
    """
    remote_dir = temp_files['remote_src_dir']
    local_dst_dir = temp_files['local_dst_dir']

    basename = os.path.basename(os.path.normpath(remote_dir))
    local_dir = os.path.join(local_dst_dir, basename)

    logger.debug('==== scp get directory ====')

    cmd = 'scp -r {}@{}:{} {}'.format(user, host, remote_dir, local_dst_dir)

    _run_scp_command(cmd, user, host, password)
    retry(validate_transfer, local_path=local_dir, remote_path=remote_dir,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_scp_get_file(host, user, password, temp_files):
    """
    Test scp copy a single file from remote:
        $ scp user@remote:/src/file/path dst/path
    """
    remote_file = temp_files['remote_src_file']
    local_dst_dir = temp_files['local_dst_dir']
    basename = os.path.basename(os.path.normpath(remote_file))
    local_file = os.path.join(local_dst_dir, basename)

    logger.debug('==== scp get a single file ====')

    cmd = 'scp {}@{}:{} {}'.format(user, host, remote_file, local_dst_dir)
    _run_scp_command(cmd, user, host, password)

    retry(validate_transfer, local_path=local_file, remote_path=remote_file,
          user=user, host=host, password=password, tries=3, interval=1)


def _test_scp_get_files(host, user, password, temp_files, file_prefix='file'):
    """
    Test scp copy several files from remote:
        $ scp user@remote:path/to/files/{file1,file2,file3} dst/path
    """
    logger.debug('==== scp get multiple files ====')

    files = temp_files['remote_files']
    remote_path = temp_files['remote_src_dir']
    local_path = temp_files['local_dst_dir']

    cmd = 'scp {}@{}:{}/{{{}}} {}'.format(user, host, remote_path,
                                          ','.join(files), local_path)

    _run_scp_command(cmd, user, host, password)

    remote_files = [os.path.join(temp_files['remote_src_dir'], f)
                    for f in temp_files['remote_files']]

    local_files = [os.path.join(local_path, '{}'.format(os.path.basename(f)))
                   for f in remote_files]
    remote_files = [os.path.join(remote_path, f) for f in files]
    # validate each file separately
    for local_path, remote_path in zip(local_files, remote_files):
        retry(
            validate_transfer, local_path=local_path, remote_path=remote_path,
            user=user, host=host, password=password, tries=3, interval=1
        )


def _test_ssh_commands(host, user, password):
    """
    Test different types of ssh commands:
        $ ssh user@host ls -d /usr
        $ ssh user@host whoami
        $ ssh -t user@host ls -d /var
        $ echo "ls -d /tmp" | ssh user@host bash
    """
    def _assert_ssh_cmd_output_expected(cmd, expected=['root'],
                                        using_bashc=False):
        def _assertion():
            out = _run_ssh_pexpect(cmd, password, using_bashc)
            for t in expected:
                assert t in out
        retry(_assertion, tries=3, interval=1)
        logger.debug(u'{}Validation: OK{}'.format(Fore.GREEN, Style.RESET_ALL))

    logger.debug('==== various ssh commands ====')
    data = [
        ('ssh {}@{} ls -d /usr'.format(user, host), ['/usr'], False),
        ('ssh {}@{} whoami'.format(user, host), ['root'], False),
        ('ssh -t {}@{} ls -d /var'.format(user, host), [
            '/var', 'Connection to {} closed.'.format(host)], False),
        ('echo "ls -d /tmp" | ssh {}@{} bash'.format(user, host),
            ['/tmp'], True)
    ]
    for cmd, expected, bash in data:
        _assert_ssh_cmd_output_expected(cmd, expected, bash)


def _test_ssh_bash(host, user, password):
    """
    Test ssh bash
    """
    logger.debug('==== ssh bash ====')

    cmd = 'ssh {}@{} /bin/bash'.format(user, host)
    ssh_cli = pexpect.spawn(cmd)
    i = ssh_cli.expect(['[Pp]assword: ', '\(yes/no\)\? '])
    if i == 1:
        ssh_cli.sendline('yes')
        ssh_cli.pexpect('[Ppassword]: ')
    ssh_cli.sendline(password)
    time.sleep(1)
    ssh_cli.expect('[\r\n]+')

    ssh_cli.sendline('pwd')
    ssh_cli.expect('/[\w\-\.]*')
    logger.debug(u'{}{}{}{}'.format(Fore.YELLOW, ssh_cli.before, ssh_cli.after,
                 Style.RESET_ALL))

    ssh_cli.sendline('cd /root')
    ssh_cli.expect('/root')
    logger.debug(u'{}{}{}{}'.format(Fore.YELLOW, ssh_cli.before, ssh_cli.after,
                 Style.RESET_ALL))

    ssh_cli.sendline('pwd')
    ssh_cli.expect('/root')
    output = ssh_cli.before + ssh_cli.after
    assert ('/root' in output)

    ssh_cli.sendline('mkdir -p tmp')
    output = ''
    ssh_cli.expect('tmp')
    ssh_cli.sendline('ls -l')
    ssh_cli.expect('total [0-9]+')
    output = ssh_cli.before + ssh_cli.after
    ssh_cli.expect('[-dxrw\.]+.*tmp')
    output += ssh_cli.before + ssh_cli.after
    ssh_cli.expect('[-dxrw\.]*.*')
    output += ssh_cli.before + ssh_cli.after
    assert ('total' in output and 'tmp' in output)
    logger.debug(u'{}{}{}'.format(Fore.YELLOW, output, Style.RESET_ALL))

    ssh_cli.sendline('ls -l /')
    output = ''
    ssh_cli.expect('total [0-9]+')
    output = ssh_cli.before + ssh_cli.after
    ssh_cli.expect('[-dxrw\.]+.*')
    output += ssh_cli.before + ssh_cli.after
    assert ('total' in output and 'root' in output)
    logger.debug(u'{}{}{}'.format(Fore.YELLOW, output, Style.RESET_ALL))
    ssh_cli.sendline('exit')
    ssh_cli.expect([pexpect.EOF, pexpect.TIMEOUT], timeout=5)
    # Expected behavior is to get pexpect.EOF, but due to a bug in docker
    # we have to send an additional new line or Ctrl^C
    if ssh_cli.isalive():
        ssh_cli.close()
    logger.debug(u'{}Validation: OK{}'.format(Fore.GREEN, Style.RESET_ALL))


def _test_ssh_with_wrong_credentials(host, user, password):
    """
    try to ssh with wrong credentials:
    1) wrong password
    2) 'root' user
    """
    logger.debug('==== ssh with wrong credentials ====')
    # Try to login using wrong password
    wrong_pass = get_rnd_string(prefix='password')
    cmd = 'ssh -o PreferredAuthentications=password -o ' \
          'PubkeyAuthentication=no {}@{}'.format(user, host)
    ssh_cli = pexpect.spawn(cmd)
    i = ssh_cli.expect(['(yes/no)? ', '[Pp]assword: '])
    if i == 0:
        ssh_cli.sendline('yes')
    ssh_cli.sendline(wrong_pass)
    ssh_cli.expect('Permission denied, please try again.')
    ssh_cli.expect('[Pp]assword: ')
    ssh_cli.sendline(wrong_pass)
    ssh_cli.expect('Permission denied, please try again.')
    ssh_cli.expect('[Pp]assword: ')
    if ssh_cli.isalive():
        ssh_cli.close()

    # Try to login with root
    cmd = 'ssh -o PreferredAuthentications=password -o ' \
          'PubkeyAuthentication=no root@{}'.format(host)
    ssh_cli = pexpect.spawn(cmd)
    i = ssh_cli.expect(['(yes/no)? ', '[Pp]assword: '])
    if i == 0:
        ssh_cli.sendline('yes')
        ssh_cli.expect('[Pp]assword: ')
    ssh_cli.sendline(password)
    ssh_cli.expect('Permission denied, please try again.')
    ssh_cli.expect('[Pp]assword: ')
    ssh_cli.sendline(password)
    ssh_cli.expect('Permission denied, please try again.')
    ssh_cli.expect('[Pp]assword: ')
    if ssh_cli.isalive():
        ssh_cli.close()


def _test_ssh_to_stopped_container(host, user, password):
    """
    Try to ssh into stopped containers
    """
    logger.debug('==== ssh to stopped containers ====')
    cmd = 'ssh {}@{} ls -l /'.format(user, host)

    def _assert_container_stopped(cmd, password, container_id):
        out = _run_ssh_pexpect(cmd, password)
        assert 'Container {} is not running'.format(container_id) in out

    retry(_assert_container_stopped, cmd=cmd, password=password,
          container_id=user, tries=3, interval=1)


def _run_ssh_pexpect(cmd, password, using_bashc=False):
    """
    Run a given command using pexpect.
    """
    logger.debug(u'{}SSH Command: {}{}'.format(Style.DIM, cmd,
                                               Style.RESET_ALL))
    if using_bashc:
        ssh_cli = pexpect.spawn('/bin/bash', ['-c', cmd])
    else:
        ssh_cli = pexpect.spawn(cmd)

    i = ssh_cli.expect(['[Pp]assword: ', '\(yes/no\)\? '])
    if i == 1:
        ssh_cli.sendline('yes')
        ssh_cli.expect('[Pp]assword: ')
    ssh_cli.sendline(password)
    time.sleep(1)

    ssh_cli.expect(['Connection to [0-9\.a-z]+ is closed.', pexpect.EOF,
                    pexpect.TIMEOUT], timeout=5)

    # Expected behavior is to get pexpect.EOF or closed connection, but due to
    # a bug in docker we have to send an additional new line or Ctrl^C
    out = str(ssh_cli.before) + str(ssh_cli.after)
    logger.debug(u'Output:\n {}{}{}'.format(Fore.YELLOW, out, Style.RESET_ALL))

    if ssh_cli.isalive():
        ssh_cli.close()

    return out


def _run_scp_command(cmd, user, host, password):
    """
    Emulate user command line interation using SCP protocol
    :param cmd: command to be executed
    :param user: remote host user
    :param host: remote host IP/hostname
    :param password: passwrod for remote user on host
    :returns None:
    """
    logger.debug(u'{}Running SCP: {}{}'.format(
        Style.DIM, cmd, Style.RESET_ALL))
    scp = pexpect.spawn(cmd)
    i = scp.expect(['\(yes/no\)\? ', '[Pp]assword: '])
    if i == 0:
        scp.sendline('yes')
        scp.expect('[Pp]assword: ')
    scp.sendline(password)
    time.sleep(1)
    try:
        while True:
            i = scp.expect([pexpect.EOF, '[0-9][0-9]:[0-9][0-9]   '],
                           timeout=5)
            if i == 0:
                logger.debug(u'{}{}{}'.format(Fore.YELLOW, scp.before,
                                              Style.RESET_ALL))
                break
            logger.debug(u'{}{}{}{}'.format(Fore.YELLOW, scp.before,
                                            scp.after, Style.RESET_ALL))
            time.sleep(.1)
    except pexpect.TIMEOUT:
        # A docker bug expecting an extra new line in the end. Ideally we
        # will exit the loop getting pexpect.EOF, i.e. i==0
        logger.debug(u'{}{}{}'.format(Fore.YELLOW, scp.before,
                                      Style.RESET_ALL))
    finally:
        if scp.isalive():
            scp.close()


def _sftp_communicate(src_path, dst_path, user, host, password, command='put'):
    """
    Emulate user command line interation throug SFTP protocol

    :param src_path: path to a source file/directory
    :param dst_path: path to a destination file/directory
    :param user: username on a remote server
    :param host: hostname of the remote server
    :param password: password for user on the remote server
    :param command: 'put' or 'get'
    :returns: None
    """
    sftp_cli = pexpect.spawn('sftp {}@{}'.format(user, host))
    i = sftp_cli.expect(['\(yes/no\)\? ', '[Pp]assword: '])
    if i == 0:
        sftp_cli.sendline('yes')
        sftp_cli.expect('[Pp]assword: ')
    sftp_cli.sendline(password)
    time.sleep(1)
    sftp_cli.expect('sftp> ')
    if command == 'put':
        if not os.path.isfile(src_path):
            sftp_cli.sendline('mkdir {}'.format(dst_path))
            sftp_cli.expect('sftp> ')
            basename = os.path.basename(os.path.normpath(src_path))
            target_dir = os.path.join(dst_path, basename)

            sftp_cli.sendline('mkdir {}'.format(target_dir))
            sftp_cli.expect('sftp> ')
            logger.debug(u'{}{}{}'.format(Fore.YELLOW, sftp_cli.before,
                                          Style.RESET_ALL))
            sftp_cli.sendline('cd {}'.format(target_dir))
            sftp_cli.expect('sftp> ')
            sftp_cli.sendline('put -r {}/*'.format(src_path))
        else:
            logger.debug(u'{}SFTP: put {} {}{}'.format(
                Style.DIM, src_path, dst_path, Style.RESET_ALL))
            sftp_cli.sendline('put {} {}'.format(src_path, dst_path))
    else:
        sftp_cli.sendline('get -r {} {}'.format(src_path, dst_path))
        logger.debug('{} SFTP: get -r {} {}{}'.format(
            Style.DIM, src_path, dst_path, Style.RESET_ALL))
    sftp_cli.expect('sftp> ')
    logger.debug(u'{}{}{}'.format(Fore.YELLOW, sftp_cli.before,
                                  Style.RESET_ALL))
    sftp_cli.sendline('bye')
    if sftp_cli.isalive():
        sftp_cli.close()


def validate_transfer(local_path, remote_path, user, host, password):
    """
    Validate that sftp transfer worked correctly. Check corresponding files.
    :param local_path: path to file/directory on the local server
    :param remote_path: path to file/directory on the remote server
    :param user: user on the remote server
    :param host: hostname/IP of the remote server
    :param password: password for user on the remote server
    :returns: None
    """
    directory = not os.path.isfile(local_path)
    if not directory:
        with get_ssh(host, user, password) as conn:
            assert _compare_files(local_path, remote_path, conn)
    else:
        # Sometimes ssh_exec exits with a 0 code, but no stdout can be read,
        # so we moved the find call inside a function.
        # Find files on a remote server at a specified path
        def _find_files(ssh, path):
            remote_cmd = 'find {} -type f'.format(path)
            ret_code, out, err = ssh_exec(
                ssh=conn, cmd=remote_cmd, get_pty=True)
            _remote_files = [f.strip() for f in out.strip().split('\n')]
            assert any(_remote_files)
            return _remote_files

        # Get file-names on the remote server
        with get_ssh(host, user, password) as conn:
            remote_files = retry(_find_files, ssh=conn, path=remote_path,
                                 tries=3, interval=1)

        # Get file names on the local server
        local_files = [os.path.join(d, p) for d, s, ps in os.walk(local_path)
                       for p in ps]

        # Make sure the number of files is the same
        if len(local_files) != len(remote_files):
            loc_msg = '\n'.join(local_files)
            rem_msg = '\n'.join(remote_files)
            logger.debug(u'\n{}Local files:\n{}{}'.format(
                Fore.RED, loc_msg, Style.RESET_ALL))
            logger.debug(u'\n{}Remote files:\n{}{}'.format(
                Fore.RED, rem_msg, Style.RESET_ALL))
            message = 'Number of files differ'
            raise FileTransferValidationFailed(message)

        try:
            with get_ssh(host, user, password) as conn:
                # Validate directories
                assert _compare_dirs(
                    local_path=local_path, remote_path=remote_path, ssh=conn
                )
                # Validate file hashes
                local_files = sorted(local_files)
                remote_files = sorted(remote_files)
                for local_path, remote_path in zip(local_files, remote_files):
                    assert _compare_files(local_path, remote_path, conn)
        except Exception as e:
            raise e


def _compare_files(local_path, remote_path, ssh):
    """
    Compare hashes of two files, one on local and another one on remote server
    :param local_path: path to file on the local server
    :param remote_path: path to file on the remote server
    :param ssh: SSHClient instance to communicate with remote server
    :returns: True/False on success/fail
    :rtype: bool
    """
    logger.debug(u'{}Comparing files. host: {} and container: {}{}'.format(
        Style.DIM, local_path, remote_path, Style.RESET_ALL))

    # Sometimes ssh_exec exits with a 0 code, but no stdout can be read,
    # so we moved the file hash call inside a function.
    def _remote_md5sum(ssh, path):
        remote_cmd = 'md5sum {}'.format(path)
        ret_code, out, err = ssh_exec(ssh=ssh, cmd=remote_cmd, get_pty=True)
        _remote_file_hash = out.strip().split()[0].strip()
        return _remote_file_hash

    # Get hash of the remote file.
    remote_file_hash = retry(_remote_md5sum, ssh=ssh, path=remote_path,
                             tries=3, interval=1)
    # Get hash of the local file
    try:
        with open(local_path) as f:
            local_file_hash = hashlib.md5(f.read()).hexdigest()
    except (OSError, IOError) as e:
        raise FileTransferValidationFailed(str(e))

    # Compare hashes
    if local_file_hash != remote_file_hash:
        message = 'Hashes not equal. Host: {} != container: {}'.format(
            local_file_hash, remote_file_hash)
        logger.debug(u'{}host: {} container: {}{}'.format(
            Fore.RED, local_path, remote_path, Style.RESET_ALL))
        raise FileTransferValidationFailed(message)
    logger.debug(u'{}Validation: OK{}'.format(Fore.GREEN, Style.RESET_ALL))
    return True


def _compare_dirs(local_path, remote_path, ssh):
    """
    Compare directories on the local and remote servers
    :param local_path: path to the directory on a local server
    :param remote_path: path to the directory on a remote server
    :returns: True/False on success/fail
    :rtype: bool
    """
    # Sometimes ssh_exec exits with a 0 code, but no stdout can be read,
    # so we moved the find call inside a function.
    # Find directories on a remote server at a specified path
    def _find_dirs(ssh, path):
        remote_cmd = 'find {} -type d'.format(path)
        ret_code, out, err = ssh_exec(ssh=ssh, cmd=remote_cmd, get_pty=True)
        _remote_dirs = {d.strip() for d in out.strip().split('\n')}
        assert any(_remote_dirs)
        return _remote_dirs

    # Get directories on the remote server
    remote_dirs = retry(_find_dirs, ssh=ssh, path=remote_path, tries=3,
                        interval=1)

    # Get directories on the local server
    local_dirs = {r for r, d, f in os.walk(local_path)}

    # Error if number of directories differ
    if local_dirs != remote_dirs:
        loc_msg = '\n'.join(local_dirs)
        rem_msg = '\n'.join(remote_dirs)
        logger.debug(u'\n{}Host dirs:\n{}{}'.format(
            Fore.RED, loc_msg, Style.RESET_ALL))
        logger.debug(u'\n{}Container dirs:\n{}{}'.format(
            Fore.RED, rem_msg, Style.RESET_ALL))
        message = 'Number of directories differ'
        raise FileTransferValidationFailed(message)

    return True


def _rmtree(sftp, path):
    for f in sftp.listdir(path):
        try:
            sftp.remove(os.path.join(path, f))
        except IOError:
            _rmtree(sftp, os.path.join(path, f))


def _create_container_files(ssh, temp_files):
    sftp = ssh.open_sftp()
    # Create source file
    dir_path = os.path.dirname(os.path.normpath(temp_files['remote_src_file']))
    _mkdir_p(sftp, dir_path)
    sftp.put(temp_files['remote_src_file'], temp_files['remote_src_file'],
             confirm=True)

    # Create source directories
    dir_path = os.path.normpath(temp_files['remote_src_subdir'])
    _mkdir_p(sftp, dir_path)
    for f in temp_files['remote_files']:
        f_ = os.path.join(temp_files['remote_src_dir'], f)
        sftp.put(f_, f_, confirm=True)

    # Create destination file
    dir_path = os.path.dirname(os.path.normpath(temp_files['remote_dst_file']))
    _mkdir_p(sftp, dir_path)
    sftp.put(temp_files['remote_dst_file'], temp_files['remote_dst_file'],
             confirm=True)

    # Create destination directories
    _mkdir_p(sftp, temp_files['remote_dst_dir'])

    sftp.close()


def _mkdir_p(sftp, path):
    path = os.path.normpath(path)
    dir_path = ''
    for dir_folder in path.split('/'):
        if dir_folder == '':
            continue
        dir_path += '/{}'.format(dir_folder)
        try:
            sftp.listdir(dir_path)
        except IOError:
            sftp.mkdir(dir_path)

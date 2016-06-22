from fabric.operations import put, run

KD_SCRIPTS_PATH_SRC = '/var/opt/kuberdock/node_scripts/'
KD_SCRIPTS_PATH = '/var/lib/kuberdock/scripts/'

SSHD_CONFIG_CMD =\
"""\
printf 'Match group kddockersshuser
  PasswordAuthentication yes
  X11Forwarding no
  AllowTcpForwarding no
  ForceCommand /var/lib/kuberdock/scripts/kd-ssh-user.sh\\n' >> /etc/ssh/sshd_config
"""

ADD_CRON_CMD =\
"""\
KD_SSH_GC_PATH="/var/lib/kuberdock/scripts/kd-ssh-gc"
KD_SSH_GC_LOCK="/var/run/kuberdock-ssh-gc.lock"
KD_SSH_GC_CMD="flock -n $KD_SSH_GC_LOCK -c '$KD_SSH_GC_PATH;rm $KD_SSH_GC_LOCK'"
KD_SSH_GC_CRON="@hourly  $KD_SSH_GC_CMD >/dev/null 2>&1"
(crontab -l 2>/dev/null; echo "$KD_SSH_GC_CRON")| crontab -
"""


def upgrade(upd, with_testing, *args, **kwargs):
    pass


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Copy KD ssh related scripts...')
    for scr in ('kd-docker-exec.sh', 'kd-ssh-gc', 'kd-ssh-user.sh',
                'kd-ssh-user-update.sh'):
        put(KD_SCRIPTS_PATH_SRC + scr, KD_SCRIPTS_PATH + scr)
        run('chmod +x {}'.format(KD_SCRIPTS_PATH + scr))

    upd.print_log('Configure sshd and cron...')
    run('groupadd kddockersshuser')
    run("echo '%kddockersshuser ALL=(ALL) NOPASSWD: "
        "/var/lib/kuberdock/scripts/kd-docker-exec.sh' >> /etc/sudoers")
    run("echo 'Defaults:%kddockersshuser !requiretty' >> /etc/sudoers")
    run(SSHD_CONFIG_CMD)
    run(ADD_CRON_CMD)

    run('systemctl restart sshd.service')


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Nothing to downgrade')

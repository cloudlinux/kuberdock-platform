from fabric.api import run, local

OVERRIDE_CONF = """\
[Service]
Restart=always
RestartSec=1s\
"""

SERVICE_DIR = "/etc/systemd/system/ntpd.service.d"
OVERRIDE_FILE = SERVICE_DIR + "/restart.conf"

def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Enabling restart for ntpd.service on master')
    local('mkdir -p ' + SERVICE_DIR)
    local('echo -e "'+OVERRIDE_CONF+'" > '+OVERRIDE_FILE)
    local('systemctl daemon-reload')
    local('systemctl restart ntpd')

def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Disabling restart for ntpd.service on master')
    local('rm -f '+OVERRIDE_FILE)
    local('systemctl daemon-reload')

def upgrade_node(upd, with_testing, env, *args, **kwargs):
    upd.print_log('Enabling restart for ntpd.service')
    run('mkdir -p ' + SERVICE_DIR)
    run('echo -e "'+OVERRIDE_CONF+'" > '+OVERRIDE_FILE)
    run('systemctl daemon-reload')
    run('systemctl restart ntpd')

def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    upd.print_log('Disabling restart for ntpd.service')
    run('rm -f '+OVERRIDE_FILE)
    run('systemctl daemon-reload')

from fabric.api import run
from kubedock.updates.helpers import install_package, reboot_node, UpgradeError

old_version = "3.10.0-229.11.1.el7.centos"


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('No upgrade provided for master')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('No downgrade provided for master')


def upgrade_node(upd, with_testing, *args, **kwargs):
    yum_base_no_kube = 'yum install --disablerepo=kube -y '
    
    run(yum_base_no_kube + 'kernel')
    run(yum_base_no_kube + 'kernel-tools')
    run(yum_base_no_kube + 'kernel-tools-libs')
    run(yum_base_no_kube + 'kernel-headers')
    run(yum_base_no_kube + 'kernel-devel')

    run('rpm -e -v --nodeps kernel-' + old_version)
    run('yum remove -y kernel-tools-' + old_version)
    run('yum remove -y kernel-tools-libs-' + old_version)
    run('yum remove -y kernel-headers-' + old_version)
    run('yum remove -y kernel-devel-' + old_version)
    reboot_node(upd)


def downgrade_node(upd, with_testing,  exception, *args, **kwargs):
    install_package('kernel-'+old_version, action='upgrade')
    install_package('kernel-tools-'+old_version, action='upgrade')
    install_package('kernel-tools-libs-'+old_version, action='upgrade')
    install_package('kernel-headers-'+old_version, action='upgrade')
    install_package('kernel-devel-'+old_version, action='upgrade')
    reboot_node(upd)

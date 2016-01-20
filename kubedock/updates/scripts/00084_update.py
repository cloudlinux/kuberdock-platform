from fabric.api import run

def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Upgrading kernel')
    upd.print_log(run("yum install -y kernel-{,-devel,-headers,-tools,-tools-libs}-3.10.0-327.4.4.el7"))
    upd.print_log(run("yum remove -y kernel{,-devel,-headers,-tools,-tools-libs}-3.10.0-229.11.1.el7.centos"))

def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Rolling back kernel')
    upd.print_log(run("yum install -y kernel{,-devel,-headers,-tools,-tools-libs}-3.10.0-229.11.1.el7.centos"))
    upd.print_log(run("yum remove -y kernel-{,-devel,-headers,-tools,-tools-libs}-3.10.0-327.4.4.el7"))

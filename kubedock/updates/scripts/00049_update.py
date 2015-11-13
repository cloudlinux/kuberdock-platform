import json
from kubedock.static_pages.models import MenuItem


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add menus Persistent volumes and Public IPs')
    public_ips = MenuItem.create(name="Public IPs", path="/publicIPs/",
                                 ordering=1, menu_id=1,
                                 roles=json.dumps(["User", "TrialUser"]))
    public_ips.save()
    p = MenuItem.create(name="Persistent volumes", path="/persistent-volumes/",
                        ordering=2, menu_id=1,
                        roles=json.dumps(["User", "TrialUser"]))
    p.save()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Delete menus Persistent volumes and Public IPs')
    ps = MenuItem.filter(MenuItem.name == 'Persistent volumes').first()
    if ps:
        ps.delete()
    pip = MenuItem.filter(MenuItem.name == 'Public IPs').first()
    if pip:
        pip.delete()

import json
from kubedock.static_pages.models import MenuItem


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add menu item Pods for the TrialUser...')
    menu_item = MenuItem.query.filter_by(name='Pods').first()
    menu_item.roles = json.dumps(json.loads(menu_item.roles) + ['TrialUser'])
    menu_item.save()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    upd.print_log('Remove menu item Pods for the TrialUser...')
    menu_item = MenuItem.query.filter_by(name='Pods').first()
    menu_item.roles = json.dumps([role for role in json.loads(menu_item.roles)
                                  if role != 'TrialUser'])
    menu_item.save()

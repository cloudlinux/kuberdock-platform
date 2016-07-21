from kubedock.rbac import fixtures as rbac_fixtures

new_permissions = [
    ('pods', 'Admin', 'dump', True),
    ('pods', 'LimitedUser', 'dump', False),
    ('pods', 'TrialUser', 'dump', False),
    ('pods', 'User', 'dump', False),
]


def upgrade(upd, *args, **kwargs):
    upd.print_log('Upgrade permissions')
    rbac_fixtures._add_permissions(new_permissions)


def downgrade(upd, *args, **kwargs):
    upd.print_log('Downgrade permissions')
    rbac_fixtures._delete_permissions(new_permissions)

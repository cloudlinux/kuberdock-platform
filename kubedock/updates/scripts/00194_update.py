"""Upgrade permissions for yaml_pods"""
from kubedock.rbac import fixtures as rbac_fixtures

new_permissions = [
    ('yaml_pods', 'Admin', 'create_non_owned', True),
    ('yaml_pods', 'User', 'create_non_owned', False),
    ('yaml_pods', 'LimitedUser', 'create_non_owned', False),
    ('yaml_pods', 'TrialUser', 'create_non_owned', False),
]


def upgrade(upd, *args, **kwargs):
    upd.print_log('Upgrade permissions')
    rbac_fixtures._add_permissions(new_permissions)


def downgrade(upd, *args, **kwargs):
    upd.print_log('Downgrade permissions')
    rbac_fixtures._delete_permissions(new_permissions)

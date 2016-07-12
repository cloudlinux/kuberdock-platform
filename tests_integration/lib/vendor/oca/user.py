# -*- coding: UTF-8 -*-
from pool import Pool, PoolElement, Template, extractString


class User(PoolElement):
    METHODS = {
        'info':      'user.info',
        'allocate':  'user.allocate',
        'delete':    'user.delete',
        'passwd':    'user.passwd',
        'chgrp':     'user.chgrp'
    }

    XML_TYPES = {
            'id':          int,
            'gid':         int,
            'group_ids':   ['GROUPS', lambda group_ids: map(lambda group_id: int(group_id.text), group_ids)],
            'gname':       extractString,
            'name':        extractString,
            'password':    extractString,
            'auth_driver': extractString,
            'enabled':     bool,
            'template':    ['TEMPLATE', Template],
            #'datastore_quota': handled separately # see http://dev.opennebula.org/issues/3849
            #'network_quota': handled separately   # see http://dev.opennebula.org/issues/3849
            #'vm_quota': handled separately        # see http://dev.opennebula.org/issues/3849
            #'image_quota'                         # see http://dev.opennebula.org/issues/3849
            #'default_user_quotas'                 # see http://dev.opennebula.org/issues/3849
    }

    ELEMENT_NAME = 'USER'

    @staticmethod
    def allocate(client, user, password):
        '''
        allocates a new user in OpenNebula

        ``user``
           username for the new user

        ``password``
           password for the new user
        '''
        user_id = client.call(User.METHODS['allocate'], user, password)
        return user_id

    def __init__(self, xml, client):
        super(User, self).__init__(xml, client)
        self.id = self['ID'] if self['ID'] else None

    def change_passwd(self, new_password):
        '''
        Changes the password for the given user.

        ``new_password``
           The new password
        '''
        self.client.call(User.METHODS['passwd'], self.id, new_password)

    def chgrp(self, gid):
        '''
        Changes the main group

        ``gid``
            New group id. Set to -1 to leave the current one
        '''
        self.client.call(User.METHODS['chgrp'], self.id, gid)

    def __repr__(self):
        return '<oca.User("%s")>' % self.name


class UserPool(Pool):
    METHODS = {
            'info':  'userpool.info',
    }

    def __init__(self, client):
        super(UserPool, self).__init__('USER_POOL', 'USER', client)

    def _factory(self, xml):
        u = User(xml, self.client)
        u._convert_types()
        return u


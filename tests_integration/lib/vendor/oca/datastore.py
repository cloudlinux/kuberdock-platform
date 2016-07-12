# -*- coding: UTF-8 -*-
from pool import Pool, PoolElement, Template, extractString

class Datastore(PoolElement):
    METHODS = {
        #'info'     : 'datastore.info',
        'allocate' : 'datastore.allocate',
        'delete'   : 'datastore.delete',
        #'enable'   : 'datastore.enable',
        #'update'   : 'datastore.update'
    }

    XML_TYPES = {
        'id'            : int,
        'name'          : extractString,
        'uid'           : int,
        'gid'           : int,
        'uname'         : extractString,
        'gname'         : extractString,
        #'permissions'   : Permissions,
        'ds_mad'        : extractString,
        'tm_mad'        : extractString,
        'base_path'     : extractString,
        'type'          : int,
        'disk_type'     : int,
        #'state'         : ???,
        'cluster_id'    : int,
        'cluster'       : extractString,
        'total_mb'      : int,
        'free_mb'       : int,
        'used_mb'       : int,
        'image_ids'     : ['IMAGES', lambda images: map(lambda image_id: int(image_id.text), images)],
        'template'      : ['TEMPLATE', Template],
    }

    ELEMENT_NAME = 'DATASTORE'

    @staticmethod
    def allocate(client, datastore_template):
        '''
        Adds a datastore to the datastore list

        Arguments

        ``datastore_template``
           Template for the datastore to add
        '''
        datastore_id = client.call(Datastore.METHODS['allocate'], datastore_template)
        return datastore_id

    def __init__(self, xml, client):
        super(Datastore, self).__init__(xml, client)
        self._convert_types()

    def __repr__(self):
        return '<oca.Datastore("%s")>' % self.name


class DatastorePool(Pool):
    METHODS = {
            'info' : 'datastorepool.info',
    }

    def __init__(self, client):
        super(DatastorePool, self).__init__('DATASTORE_POOL', 'DATASTORE', client)

    def _factory(self, xml):
        c = Datastore(xml, self.client)
        return c

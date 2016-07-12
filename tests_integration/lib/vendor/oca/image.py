# -*- coding: UTF-8 -*-
from pool import Pool, PoolElement, Template, extractString


class Image(PoolElement):
    METHODS = {
        'info'     : 'image.info',
        'allocate' : 'image.allocate',
        'delete'   : 'image.delete',
        'update'   : 'image.update',
        'enable'   : 'image.enable',
        'publish'  : 'image.publish',
        'chown'    : 'image.chown',
        'persistent'  : 'image.persistent',
    }

    XML_TYPES = {
            'id'          : int,
            'uid'         : int,
            'gid'         : int,
            'uname'       : extractString,
            'gname'       : extractString,
            'name'        : extractString,
            #'permissions' : ???,
            'type'        : int,
            'disk_type'   : int,
            'persistent'  : int,
            'regtime'     : int,
            'source'      : extractString,
            'path'        : extractString,
            'fstype'      : extractString,
            'size'        : int,
            'state'       : int,
            'running_vms' : int,
            'cloning_ops' : int,
            'cloning_id'  : int,
            'datastore_id': int,
            'datastore'   : extractString,
            'vm_ids'      : ["VMS", lambda vms: map(lambda vm_id: int(vm_id.text), vms)],
            'clone_ids'   : ["CLONES", lambda clones: map(lambda clone_id: int(clone_id.text), clones)],
            'template'    : ['TEMPLATE', Template],
    }

    INIT = 0
    READY = 1
    USED = 2
    DISABLED = 3
    IMAGE_STATES = ['INIT', 'READY', 'USED', 'DISABLED']

    SHORT_IMAGE_STATES = {
            "INIT"      : "init",
            "READY"     : "rdy",
            "USED"      : "used",
            "DISABLED"  : "disa"
    }

    IMAGE_TYPES = ['OS', 'CDROM', 'DATABLOCK']

    SHORT_IMAGE_TYPES = {
            "OS"         : "OS",
            "CDROM"      : "CD",
            "DATABLOCK"  : "DB"
    }

    ELEMENT_NAME = 'IMAGE'

    @staticmethod
    def allocate(client, template):
        '''
        Allocates a new image in OpenNebula

        Arguments

        ``client``
           oca.Client object

        ``template``
           a string containing the template of the image
        '''
        image_id = client.call(Image.METHODS['allocate'], template)
        return image_id

    def __init__(self, xml, client):
        super(Image, self).__init__(xml, client)
        self.id = self['ID'] if self['ID'] else None

    def update(self, template):
        '''
        Replaces the template contents

        Arguments

        ``template``
            New template contents
        '''
        self.client.call(self.METHODS['update'], self.id, template)

    def enable(self):
        '''
        Enables an image
        '''
        self.client.call(self.METHODS['enable'], self.id, True)

    def disable(self):
        '''
        Disables an image
        '''
        self.client.call(self.METHODS['enable'], self.id, False)

    def publish(self):
        '''
        Publishes an image
        '''
        self.client.call(self.METHODS['publish'], self.id, True)

    def unpublish(self):
        '''
        Unpublishes an image
        '''
        self.client.call(self.METHODS['publish'], self.id, False)

    def set_persistent(self):
        '''
        Set Image as persistent
        '''
        self.client.call(self.METHODS['persistent'], self.id, True)

    def set_nonpersistent(self):
        '''
        Set Image as non persistent
        '''
        self.client.call(self.METHODS['persistent'], self.id, False)

    def chown(self, uid, gid):
        '''
        Changes the owner/group

        Arguments

        ``uid``
            New owner id. Set to -1 to leave current value
        ``gid``
            New group id. Set to -1 to leave current value
        '''
        self.client.call(self.METHODS['chown'], self.id, uid, gid)

    @property
    def str_state(self):
        '''
        String representation of image state.
        One of 'INIT', 'READY', 'USED', 'DISABLED'
        '''
        return self.IMAGE_STATES[int(self.state)]

    @property
    def short_state(self):
        '''
        Short string representation of image state.
        One of 'init', 'rdy', 'used', 'disa'
        '''
        return self.SHORT_IMAGE_STATES[self.str_state]

    @property
    def str_type(self):
        '''
        String representation of image type.
        One of 'OS', 'CDROM', 'DATABLOCK'
        '''
        return self.IMAGE_TYPES[int(self.type)]

    @property
    def short_type(self):
        '''
        Short string representation of image type.
        One of 'OS', 'CD', 'DB'
        '''
        return self.SHORT_IMAGE_TYPES[self.str_type]

    def __repr__(self):
        return '<oca.Image("%s")>' % self.name


class ImagePool(Pool):
    METHODS = {
            'info' : 'imagepool.info',
    }

    def __init__(self, client):
        super(ImagePool, self).__init__('IMAGE_POOL', 'IMAGE', client)

    def _factory(self, xml):
        i = Image(xml, self.client)
        i._convert_types()
        return i


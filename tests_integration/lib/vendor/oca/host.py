# -*- coding: UTF-8 -*-
from pool import Pool, PoolElement, Template, extractString


class HostShare(Template):
    def __repr__(self):
        return '<oca.vm.HostShare()>'


class Host(PoolElement):
    METHODS = {
        'info'     : 'host.info',
        'allocate' : 'host.allocate',
        'delete'   : 'host.delete',
        'enable'   : 'host.enable',
        'update'   : 'host.update'
    }

    INIT = 0
    MONITORING_MONITORED = 1 # Currently monitoring, previously MONITORED
    MONITORED = 2
    ERROR = 3
    DISABLED = 4
    MONITORING_ERROR = 5     # Currently monitoring, previously ERROR
    MONITORING_INIT = 6      # Currently monitoring, previously initialized
    MONITORING_DISABLED = 7  # Currently monitoring, previously DISABLED
    HOST_STATES = ['INIT', 'MONITORING_MONITORED', 'MONITORED', 'ERROR', 'DISABLED',
                   'MONITORING_ERROR', 'MONITORING_INIT', 'MONITORING_DISABLED']

    SHORT_HOST_STATES = {
        'INIT':                 'on',
        'MONITORING_MONITORED': 'on',
        'MONITORED':            'on',
        'ERROR':                'err',
        'DISABLED':             'off',
        'MONITORING_ERROR':     'on',
        'MONITORING_INIT':      'on',
        'MONITORING_DISABLED':  'on',
    }

    XML_TYPES = {
        'id':             int,
        'name':           extractString,
        'state':          int,
        'im_mad':         extractString,
        'vm_mad':         extractString,
        'vn_mad':         extractString,
        'last_mon_time':  int,
        'cluster':        extractString,
        'cluster_id':     int,
        'vm_ids':         ['VMS', lambda vms: map(lambda vmid: int(vmid.text), vms)],
        'template':       ['TEMPLATE', Template],
        'host_share':     ['HOST_SHARE', HostShare],
    }

    ELEMENT_NAME = 'HOST'

    @staticmethod
    def allocate(client, hostname, im, vmm, tm, cluster_id=-1):
        '''
        Adds a host to the host list

        Arguments

        ``hostname``
           Hostname machine to add

        ``im``
           Information manager'

        ``vmm``
           Virtual machine manager.

        ``tm``
           Transfer manager
        '''
        host_id = client.call(Host.METHODS['allocate'], hostname, im, vmm, tm, cluster_id)
        return host_id

    def __init__(self, xml, client):
        super(Host, self).__init__(xml, client)
        self.id = self['ID'] if self['ID'] else None

    def enable(self):
        '''
        Enable this host
        '''
        self.client.call(self.METHODS['enable'], self.id, True)

    def disable(self):
        '''
        Disable this host.
        '''
        self.client.call(self.METHODS['enable'], self.id, False)

    def update(self, template, merge=False):
        '''
        Update the template of this host. If merge is false (default),
        the existing template is replaced.
        '''
        self.client.call(self.METHODS['update'], self.id, template, 1 if merge else 0)

    @property
    def str_state(self):
        '''
        String representation of host state.
        One of 'INIT', 'MONITORING', 'MONITORED', 'ERROR', 'DISABLED'
        '''
        return self.HOST_STATES[int(self.state)]

    @property
    def short_state(self):
        '''
        Short string representation of host state. One of 'on', 'off', 'err'
        '''
        return self.SHORT_HOST_STATES[self.str_state]

    def __repr__(self):
        return '<oca.Host("%s")>' % self.name


class HostPool(Pool):
    METHODS = {
            'info' : 'hostpool.info',
    }

    def __init__(self, client):
        super(HostPool, self).__init__('HOST_POOL', 'HOST', client)

    def _factory(self, xml):
        h = Host(xml, self.client)
        h._convert_types()
        return h


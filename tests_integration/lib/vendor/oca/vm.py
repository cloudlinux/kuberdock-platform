# -*- coding: UTF-8 -*-
from pool import Pool, PoolElement, Template, extractString


class History(Template):
    def __repr__(self):
        return '<oca.vm.History("seq={0}")>'.format(self.seq)


class VirtualMachine(PoolElement):
    METHODS = {
        'info':      'vm.info',
        'allocate':  'vm.allocate',
        'action':    'vm.action',
        'migrate':   'vm.migrate',
        'deploy':    'vm.deploy',
        'savedisk':  'vm.savedisk',
        'delete':    'vm.delete',
        'chown':     'vm.chown',
        'update':    'vm.update',
    }

    INIT = 0
    PENDING = 1
    HOLD = 2
    ACTIVE = 3
    STOPPED = 4
    SUSPENDED = 5
    DONE = 6
    FAILED = 7
    VM_STATE = ['INIT', 'PENDING', 'HOLD', 'ACTIVE', 'STOPPED',
                'SUSPENDED', 'DONE', 'FAILED']

    SHORT_VM_STATES = {
        'INIT':       'init',
        'PENDING':    'pend',
        'HOLD':       'hold',
        'ACTIVE':     'actv',
        'STOPPED':    'stop',
        'SUSPENDED':  'susp',
        'DONE':       'done',
        'FAILED':     'fail'
    }

    LCM_STATE = ['LCM_INIT', 'PROLOG', 'BOOT', 'RUNNING', 'MIGRATE',
                 'SAVE_STOP', 'SAVE_SUSPEND', 'SAVE_MIGRATE',
                 'PROLOG_MIGRATE', 'PROLOG_RESUME', 'EPILOG_STOP', 'EPILOG',
                 'SHUTDOWN', 'CANCEL', 'FAILURE', 'DELETE', 'UNKNOWN']

    SHORT_LCM_STATES = {
        'LCM_INIT':       'init',
        'PROLOG':         'prol',
        'BOOT':           'boot',
        'RUNNING':        'runn',
        'MIGRATE':        'migr',
        'SAVE_STOP':      'save',
        'SAVE_SUSPEND':   'save',
        'SAVE_MIGRATE':   'save',
        'PROLOG_MIGRATE': 'migr',
        'PROLOG_RESUME':  'prol',
        'EPILOG_STOP':    'epil',
        'EPILOG':         'epil',
        'SHUTDOWN':       'shut',
        'CANCEL':         'shut',
        'FAILURE':        'fail',
        'DELETE':         'dele',
        'UNKNOWN':        'unkn',
    }

    MIGRATE_REASON = ['NONE', 'ERROR', 'STOP_RESUME', 'USER', 'CANCEL']

    SHORT_MIGRATE_REASON = {
        'NONE':           'none',
        'ERROR':          'erro',
        'STOP_RESUME':    'stop',
        'USER':           'user',
        'CANCEL':         'canc'
    }

    XML_TYPES = {
        'id':            int,
        'uid':           int,
        'gid':           int,
        'uname':         extractString,
        'gname':         extractString,
        'name':          extractString,
        #'permissions': ???,
        'last_poll':     int,
        'state':         int,
        'lcm_state':     int,
        'resched':       int,
        'stime':         int,
        'etime':         int,
        'deploy_id':     extractString,
        'template':      ['TEMPLATE', Template, ['NIC', 'DISK']],
        'user_template': ['USER_TEMPLATE', Template],
        'history_records':  ['HISTORY_RECORDS', lambda x: [History(i)
                                        for i in x] if x is not None else []],
    }

    ELEMENT_NAME = 'VM'

    @staticmethod
    def allocate(client, template):
        '''
        allocates a virtual machine description from the given template string

        Arguments

        ``template``
           a string containing the template of the vm
        '''
        vm_id = client.call(VirtualMachine.METHODS['allocate'], template)
        return vm_id

    def __init__(self, xml, client):
        super(VirtualMachine, self).__init__(xml, client)
        self.id = self['ID'] if self['ID'] else None

    def deploy(self, host_id):
        '''
        initiates the instance of the given vmid on the target host

        Arguments

        ``host_id``
           the host id (hid) of the target host where the VM will be
           instantiated.
        '''
        self.client.call(self.METHODS['deploy'], self.id, host_id)

    def migrate(self, dest_host):
        '''
        migrates virtual machine to the target host

        Arguments

        ``dest_host``
           the target host id
        '''
        self.client.call(self.METHODS['migrate'], self.id, dest_host, False)

    def live_migrate(self, dest_host):
        '''
        live migrates virtual machine to the target host

        Arguments

        ``dest_host``
           the target host id
        '''
        self.client.call(self.METHODS['migrate'], self.id, dest_host, True)

    def save_disk(self, disk_id, dest_disk):
        '''
        Sets the disk to be saved in the given image

        Arguments

        ``disk_id``
           disk id of the disk we want to save
        ``dest_disk``
           image id where the disk will be saved.
        '''
        self.client.call(self.METHODS['savedisk'], self.id, disk_id, dest_disk)

    def shutdown(self):
        '''
        Shutdowns an already deployed VM
        '''
        self._action('shutdown')

    def shutdown_hard(self):
        '''
        Shutdown hard an already deployed VM
        '''
        self._action('shutdown-hard')

    def poweroff(self):
        '''
        Power off an running vm
        '''
        self._action('poweroff')

    def poweroff_hard(self):
        '''
        Power off hard an running vm
        '''
        self._action('poweroff-hard')

    def cancel(self):
        '''
        Cancels a running VM
        '''
        self._action('cancel')

    def hold(self):
        '''
        Sets a VM to hold state, scheduler will not deploy it
        '''
        self._action('hold')

    def release(self):
        '''
        Releases a VM from hold state
        '''
        self._action('release')

    def stop(self):
        '''
        Stops a running VM
        '''
        self._action('stop')

    def suspend(self):
        '''
        Saves a running VM
        '''
        self._action('suspend')

    def resume(self):
        '''
        Resumes the execution of a saved VM
        '''
        self._action('resume')

    def finalize(self):
        '''
        Deletes a VM from the pool and DB
        '''
        self._action('finalize')

    def restart(self):
        '''
        Resubmits the VM after failure
        '''
        self._action('restart')

    def resubmit(self):
        '''
        Redeploy the VM.
        '''
        self._action('resubmit')

    def delete(self):
        '''
        Delete the VM.
        '''
        self._action('delete')

    def _action(self, action):
        self.client.call(self.METHODS['action'], action, self.id)

    def __repr__(self):
        return '<oca.VirtualMachine("%s")>' % self.name

    @property
    def str_state(self):
        '''
        String representation of virtual machine state.
        One of: INIT, PENDING, HOLD, ACTIVE, STOPPED, SUSPENDED,
        DONE, FAILED
        '''
        return self.VM_STATE[int(self.state)]

    @property
    def short_state(self):
        '''
        Short string representation of virtual machine state.
        One of: init, pend, hold, actv, stop, susp, done, fail
        '''
        return self.SHORT_VM_STATES[self.str_state]

    @property
    def str_lcm_state(self):
        '''
        String representation of virtual machine LCM state.
        One of: LCM_INIT, PROLOG, BOOT, RUNNING, MIGRATE,
        SAVE_STOP, SAVE_SUSPEND, SAVE_MIGRATE, PROLOG_MIGRATE,
        PROLOG_RESUME, EPILOG_STOP, EPILOG, SHUTDOWN, CANCEL,
        FAILURE, DELETE, UNKNOWN
        '''
        return self.LCM_STATE[int(self.lcm_state)]

    @property
    def short_lcm_state(self):
        '''
        Short string representation of virtual machine LCM state.
        One of: init, prol, boot, runn, migr, save, save,
        save, migr, prol, epil, shut, shut, fail,
        dele, unkn
        '''
        return self.SHORT_LCM_STATES[self.str_lcm_state]

    def update(self, template, merge=False):
        '''
        Update the template of this host. If merge is false (default),
        the existing template is replaced.
        '''
        self.client.call(self.METHODS['update'], self.id, template, 1 if merge else 0)


class VirtualMachinePool(Pool):
    METHODS = {
            'info' : 'vmpool.info',
    }

    def __init__(self, client):
        super(VirtualMachinePool, self).__init__('VM_POOL', 'VM', client)

    def _factory(self, xml):
        vm = VirtualMachine(xml, self.client)
        vm._convert_types()
        return vm

    def info(self, filter=-3, range_start=-1, range_end=-1, vm_state=-1):
        '''
        Retrives/Refreshes virtual machine pool information

        ``filter``
            Filter flag. By defaults retrives only connected user reources.

        ``range_start``
            Range start ID. -1 for all

        ``range_end``
            Range end ID. -1 for all

        ``vm_state``

            VM state to filter by.

            * \-2	 Any state, including DONE
            * \-1	 Any state, except DONE (Defualt)
            * 0	 INIT
            * 1	 PENDING
            * 2	 HOLD
            * 3	 ACTIVE
            * 4	 STOPPED
            * 5	 SUSPENDED
            * 6	 DONE
            * 7	 FAILED

        '''
        super(VirtualMachinePool, self).info(filter, range_start,
                                             range_end, vm_state)

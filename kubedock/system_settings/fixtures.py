import json
from .models import db, SystemSettings


def add_system_settings():
    db.session.add_all([
        SystemSettings(
            name='billing_type', label='Select your billing system',
            value='No billing', options=json.dumps(['No billing', 'WHMCS'])),
        SystemSettings(
            name='billing_url', label='Link to WHMCS',
            placeholder='http://domain.name',
            description=('Used to access billing API and to create link to '
                         'predefined application request processing script')),
        SystemSettings(
            name='billing_username', label='WHMCS admin username',
            placeholder='admin'),
        SystemSettings(
            name='billing_password', label='WHMCS admin password',
            placeholder='password'),
        SystemSettings(
            name='persitent_disk_max_size', value='10',
            label='Persistent disk maximum size',
            description='Maximum capacity of a user container persistent disk in GB',
            placeholder='Enter value to limit PD size'),
    ])

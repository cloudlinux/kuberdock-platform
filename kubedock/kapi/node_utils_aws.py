import hashlib
import socket
import time

from boto import ec2
from boto.ec2 import blockdevicemapping as ec2_bdm
from boto.ec2 import networkinterface as ec2_ni

from kubedock.core import db, ssh_connect
from kubedock.kapi.node_utils import (
    add_node_to_k8s,
    complete_calico_node_config,
)
from kubedock.nodes.models import Node
from kubedock.rbac.models import Role
from kubedock.settings import (
    AWS,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_INSTANCE_RUNNING_INTERVAL,
    AWS_INSTANCE_RUNNING_MAX_ATTEMTPS,
    FIXED_IP_POOLS,
    MASTER_IP,
    NODE_INSTALL_LOG_FILE,
    NODE_INSTALL_TIMEOUT_SEC,
    NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT,
    REGION,
    SSH_PUB_FILENAME,
    IS_PRODUCTION_PKG,
)
from kubedock.system_settings.models import SystemSettings
from kubedock.users.models import User, SessionData
from kubedock.utils import (
    NODE_STATUSES,
    get_timezone,
    get_version,
    send_event,
    send_logs,
)


CENTOS_AMI = {
    'ap-northeast-1':   'ami-eec1c380',
    'ap-northeast-2':   'ami-c74789a9',
    'ap-southeast-1':   'ami-f068a193',
    'ap-southeast-2':   'ami-fedafc9d',
    'eu-west-1':        'ami-7abd0209',
    'eu-central-1':     'ami-9bf712f4',
    'sa-east-1':        'ami-26b93b4a',
    'us-east-1':        'ami-6d1c2007',
    'us-west-1':        'ami-af4333cf',
    'us-west-2':        'ami-d2c924b2',
}


HASH_FILES = [
    'aws-kd-deploy/aws-kd-ami.sh',
    'deploy.sh',
    'kuberdock.spec',
    'node_install.sh',
    'node_install_ami.sh',
    'node_install_common.sh',
    'node_prepare_ami.sh',
]


USER_DATA_TEMPLATE = """\
#!/bin/bash
echo "{0}" > /root/.ssh/authorized_keys
"""


class AMIException(Exception):
    pass


def create_instance(image_id, node_root_disk_size, node_root_disk_type,
                    iam_profile_node_arn, node_size, subnet_id,
                    aws_ssh_key_name, security_group_ids, tags):
    connection = get_connection()

    image = connection.get_image(image_id=image_id)

    block_device = ec2_bdm.EBSBlockDeviceType()
    block_device.delete_on_termination = True
    block_device.size = node_root_disk_size
    block_device.volume_type = node_root_disk_type

    block_device_map = ec2_bdm.BlockDeviceMapping()
    block_device_map[image.root_device_name] = block_device

    network_interface = ec2_ni.NetworkInterfaceSpecification(
        subnet_id=subnet_id,
        groups=security_group_ids,
        associate_public_ip_address=True,
    )
    network_interfaces = ec2_ni.NetworkInterfaceCollection(network_interface)

    user_data = get_user_data()

    reservation = connection.run_instances(
        image_id=image_id,
        instance_profile_arn=iam_profile_node_arn,
        instance_type=node_size,
        key_name=aws_ssh_key_name,
        block_device_map=block_device_map,
        network_interfaces=network_interfaces,
        user_data=user_data,
    )

    instance = reservation.instances[0]

    connection.create_tags(resource_ids=[instance.id], tags=tags)
    instance.modify_attribute(attribute='sourceDestCheck', value=False)

    return instance


def deploy_node(node_id, log_pod_ip):
    db_node = Node.get_by_id(node_id)
    admin_rid = Role.query.filter_by(rolename='Admin').one().id
    channels = [i.id for i in SessionData.query.filter_by(role_id=admin_rid)]
    initial_evt_sent = False
    host = db_node.hostname
    kube_type = db_node.kube_id
    cpu_multiplier = SystemSettings.get_by_name('cpu_multiplier')
    memory_multiplier = SystemSettings.get_by_name('memory_multiplier')
    ku = User.get_internal()
    token = ku.get_token()
    with open(NODE_INSTALL_LOG_FILE.format(host), 'w') as log_file:
        try:
            timezone = get_timezone()
        except OSError as e:
            raise AMIException('Cannot get master timezone: {0}'.format(e))

        send_logs(
            db_node.id,
            'Connecting to {0} with ssh with user "root" ...'.format(host),
            log_file,
            channels
        )

        ssh, err = ssh_connect(host)
        if err:
            raise AMIException(err)

        sftp = ssh.open_sftp()
        sftp.get_channel().settimeout(NODE_SSH_COMMAND_SHORT_EXEC_TIMEOUT)
        sftp.put('/etc/kubernetes/configfile_for_nodes',
                 '/etc/kubernetes/configfile')
        sftp.put('/etc/pki/etcd/ca.crt', '/etc/pki/etcd/ca.crt')
        sftp.put('/etc/pki/etcd/etcd-client.crt',
                 '/etc/pki/etcd/etcd-client.crt')
        sftp.put('/etc/pki/etcd/etcd-client.key',
                 '/etc/pki/etcd/etcd-client.key')
        sftp.put('/etc/pki/etcd/etcd-dns.crt', '/etc/pki/etcd/etcd-dns.crt')
        sftp.put('/etc/pki/etcd/etcd-dns.key', '/etc/pki/etcd/etcd-dns.key')
        sftp.close()

        deploy_vars = {
            'NODE_IP': db_node.ip,
            'AWS': AWS,
            'MASTER_IP': MASTER_IP,
            'TZ': timezone,
            'NODENAME': host,
            'CPU_MULTIPLIER': cpu_multiplier,
            'MEMORY_MULTIPLIER': memory_multiplier,
            'FIXED_IP_POOLS': FIXED_IP_POOLS,
            'TOKEN': token,
            'LOG_POD_IP': log_pod_ip,
        }
        deploy_cmd = 'bash /node_install_ami.sh'

        set_vars_str = ' '.join('{key}="{value}"'.format(key=k, value=v)
                                for k, v in deploy_vars.items())
        cmd = '{set_vars} {deploy_cmd}'.format(set_vars=set_vars_str,
                                               deploy_cmd=deploy_cmd)

        s_time = time.time()
        i, o, e = ssh.exec_command(cmd,
                                   timeout=NODE_INSTALL_TIMEOUT_SEC,
                                   get_pty=True)
        try:
            while not o.channel.exit_status_ready():
                data = o.channel.recv(1024)
                while data:
                    if not initial_evt_sent:
                        send_event('node:change', {'id': db_node.id})
                        initial_evt_sent = True
                    for line in data.split('\n'):
                        send_logs(db_node.id, line, log_file, channels)
                    data = o.channel.recv(1024)
                    if (time.time() - s_time) > NODE_INSTALL_TIMEOUT_SEC:
                        raise socket.timeout()
                time.sleep(0.2)
        except socket.timeout:
            raise AMIException('Timeout hit during node install '
                               '{0} cmd'.format(cmd))

        ret_code = o.channel.recv_exit_status()
        if ret_code != 0:
            raise AMIException(
                'Node install failed cmd {0} '
                'with retcode {1}'.format(cmd, ret_code)
            )

        complete_calico_node_config(host, db_node.ip)

        time.sleep(2)

        err = add_node_to_k8s(host, kube_type)
        if err:
            raise AMIException('ERROR adding node', log_file, channels)

        send_logs(db_node.id, 'Adding Node completed successful.',
                  log_file, channels)
        send_logs(db_node.id, '===================================',
                  log_file, channels)

        ssh.close()

        db_node.state = NODE_STATUSES.completed
        db.session.commit()
        send_event('node:change', {'id': db_node.id})


def detect_ami_image(role):
    connection = get_connection()

    try:
        images = connection.get_all_images(
            filters={
                'tag:KuberDockAmiVersion': get_ami_version(),
                'tag:KuberDockClusterRole': role,
            }
        )
        image = images[0]
    except (AttributeError, IndexError, TypeError) as e:
        raise AMIException(e)

    return image


def get_ami_hash():
    md5 = hashlib.md5()
    for f in HASH_FILES:
        with open(f) as fd:
            md5.update(fd.read())
    return md5.hexdigest()[:8]


def get_ami_version():
    return get_version('kuberdock') if IS_PRODUCTION_PKG else get_ami_hash()


def get_connection():
    connection = ec2.connect_to_region(
        REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    )
    if connection is None:
        raise AMIException('Unable to connect to region {0}'.format(REGION))
    return connection


def get_instance(hostname):
    connection = get_connection()

    try:
        instances = connection.get_only_instances(
            filters={'private_dns_name': hostname}
        )
        instance = instances[0]
    except (AttributeError, IndexError, TypeError) as e:
        raise AMIException(e)

    return instance


def get_instance_profile_arn(instance):
    try:
        instance_profile_arn = instance.instance_profile['arn']
    except (AttributeError, KeyError) as e:
        raise AMIException(e)
    return instance_profile_arn


def get_nginx_id_rsa_pub():
    with open(SSH_PUB_FILENAME) as id_rsa_pub_file:
        id_rsa_pub = id_rsa_pub_file.read()
    return id_rsa_pub


def get_node_data(hostname):
    fast = True
    try:
        image = detect_ami_image('node')
    except AMIException:
        fast = False
        image = CENTOS_AMI.get(REGION)
        if image is None:
            raise AMIException(
                'There is no CentOS AMI for region {0}'.format(REGION)
            )
    instance = get_instance(hostname)
    iam_profile = get_instance_profile_arn(instance)
    root_volume = get_root_volume(instance)

    data = dict(
        image_id=image.id,
        node_root_disk_size=root_volume.size,
        node_root_disk_type=root_volume.type,
        iam_profile_node_arn=iam_profile,
        node_size=instance.instance_type,
        subnet_id=instance.subnet_id,
        aws_ssh_key_name=instance.key_name,
        security_group_ids=[group.id for group in instance.groups],
        tags=instance.tags,
    )

    return data, fast


def get_root_volume(instance):
    connection = get_connection()

    try:
        block_device = instance.block_device_mapping[instance.root_device_name]
        volumes = connection.get_all_volumes(
            filters={'volume_id': block_device.volume_id}
        )
        volume = volumes[0]
    except (AttributeError, IndexError, KeyError) as e:
        raise AMIException(e)

    return volume


def get_user_data():
    nginx_id_rsa_pub = get_nginx_id_rsa_pub()
    user_data = USER_DATA_TEMPLATE.format(nginx_id_rsa_pub)
    return user_data


def spawn_reserving_node(hostname):
    node_data, fast = get_node_data(hostname)
    instance = create_instance(**node_data)
    return instance.private_dns_name, instance.private_ip_address, fast


def terminate_node(hostname):
    instance = get_instance(hostname)
    instance.connection.terminate_instances([instance.id])


def wait_node_accessible(hostname):
    attempt = AWS_INSTANCE_RUNNING_MAX_ATTEMTPS
    while attempt > 0:
        ssh, err = ssh_connect(hostname)
        if err is None:
            break
        attempt -= 1
        time.sleep(AWS_INSTANCE_RUNNING_INTERVAL)
    else:
        raise AMIException(
            'Timeout waiting node {0} to be accessible'.format(hostname)
        )
    return ssh


def wait_node_running(hostname):
    attempt = AWS_INSTANCE_RUNNING_MAX_ATTEMTPS
    while attempt > 0:
        instance = get_instance(hostname)
        if instance.state == 'running':
            break
        attempt -= 1
        time.sleep(AWS_INSTANCE_RUNNING_INTERVAL)
    else:
        raise AMIException(
            'Timeout waiting node {0} to be running'.format(hostname)
        )


# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

import os
import re
import oca
import socket
import logging
import argparse
import paramiko
from time import sleep, time
import xml.etree.ElementTree as ET
from sys import platform as _platform

VM_ACTIVE = 3
VM_STOPPED = 4
IMAGE_READY = 1

msg_format = '%(asctime)s - %(message)s'
logging.basicConfig(
    level=logging.DEBUG,
    format=msg_format,
    filename='update_template.log',
    filemode='w')
console = logging.StreamHandler()
console.setLevel(logging.INFO)
formatter = logging.Formatter(msg_format)
console.setFormatter(formatter)
logging.getLogger().addHandler(console)


class PublicPortWaitTimeoutException(Exception):
    pass


class NebulaVMTemplate(object):
    def __init__(self, client, ssh_key_path, template_id):
        self.client = client
        self.template_id = template_id
        self.ssh_key_path = ssh_key_path
        self.template_pool = oca.VmTemplatePool(self.client)
        self.template_pool.info(filter=-2, range_start=-1, range_end=-1)
        self.image_pool = oca.ImagePool(self.client)
        self.image_pool.info(filter=-2, range_start=-1, range_end=-1)
        self.vm_pool = oca.VirtualMachinePool(self.client)
        self.vm_pool.info(filter=-2, range_start=-1, range_end=-1)

    @classmethod
    def factory(cls, url, username, password, ssh_key_path, template_id):
        client = oca.Client('{}:{}'.format(username, password), url)
        return cls(client, ssh_key_path, template_id)

    def increase_version(self, name):
        """
        Increases the number of version for template/image,
        if it is already there and appends one if not.
        """
        name = name.rstrip()
        pattern = r'v(\d+)$'
        match = re.search(pattern, name)
        if match is not None:
            number = int(match.group(1)) + 1
            version = 'v' + str(number)
            new_name = re.sub(pattern, version, name)
        else:
            new_name = name + ' v2'
        if new_name in [image.name for image in self.image_pool]:
            return self.increase_version(new_name)
        else:
            return new_name

    def debug_msg(self, msg):
        logging.debug("{0} {1} {0}".format('*' * 10, msg))

    def edit_disk(self, driver=None, image=None, image_uname=None, size=None):
        """
        Change disk settings in template
        """
        root = ET.Element('VMTEMPLATE')
        disk = ET.SubElement(root, 'DISK')
        if driver:
            drv = ET.SubElement(disk, 'DRIVER')
            drv.text = driver
        img = ET.SubElement(disk, 'IMAGE')
        img.text = image
        img_uname = ET.SubElement(disk, 'IMAGE_UNAME')
        img_uname.text = image_uname
        if size:
            sz = ET.SubElement(disk, 'SIZE')
            sz.text = size
        return ET.tostring(root)

    def wait_for_state(self, element, state):
        timeout = 60 * 5
        end = time() + timeout
        logging.info(
            'Waiting for status of {} with name {}'.format(
                element.ELEMENT_NAME,
                element.name
            ))
        while element.state != state:
            sleep(4)
            element.info()
            if time() > end:
                raise RuntimeError(
                    'Timeout for status {} of element {} exceeded'.format(
                        state, element.name))

    def wait_net_port(self, ip, port, timeout, try_interval=2):
        logging.info(
            "Waiting for {0}:{1} to become available.".format(ip, port))
        end = time() + timeout
        while time() < end:
            try:
                s = socket.create_connection((ip, port), timeout=5)
            except socket.timeout:
                # cannot connect after timeout
                continue
            except socket.error as ex:
                # cannot connect immediately (e.g. no route)
                # wait timeout before next try
                logging.info("Wait cycle msg: {0}".format(repr(ex)))
                sleep(try_interval)
                continue
            else:
                # success!
                s.close()
                return
        raise PublicPortWaitTimeoutException()

    def create_vm(self, template):
        """
        Instantiate VM from the template
        and check its status
        """
        vm_name = "template_{}_upgrade".format(self.template_id)
        logging.info('Bringing up temporary VM from {}'.format(
            template.name))
        template.instantiate(name=vm_name)
        self.vm_pool.info(filter=-2, range_start=-1, range_end=-1)
        vm = self.vm_pool.get_by_name(vm_name)
        vm.info()
        self.debug_msg('Info dump for {}'.format(self.image_pool.pool_name))
        logging.debug(ET.tostring(vm.xml))
        logging.debug('*' * 30)
        self.wait_for_state(vm, VM_ACTIVE)
        logging.info('VM with id {} is up and "Active"'.format(vm.id))
        return vm

    def delete_vm(self, vm):
        """
        Stops and deletes VM correctly
        """
        vm.stop()
        vm.info()
        logging.info('Stopping VM with id {}'.format(vm.id))
        self.wait_for_state(vm, VM_STOPPED)
        vm.finalize()
        logging.info('VM with id {} stopped and deleted'.format(vm.id))

    def clone_template(self):
        """
        Returns cloned template along with image,
        which is going to be new base image
        """
        # get original template and image
        template = self.template_pool.get_by_id(self.template_id)
        template.info()
        self.debug_msg('Info dump for {}'.format(template.name))
        logging.debug(ET.tostring(template.xml))
        logging.debug('*' * 30)
        image = self.image_pool.get_by_name(
            template.xml.find('TEMPLATE/DISK/IMAGE').text)
        image.info()
        self.debug_msg('Info dump for {}'.format(image.name))
        logging.debug(ET.tostring(image.xml))
        logging.debug('*' * 30)

        # clone template & image
        logging.info('Cloning template and image.')
        target_image_name = self.increase_version(image.name)
        image.clone(name=target_image_name)
        self.image_pool.info(filter=-2, range_start=-1, range_end=-1)
        self.debug_msg('Info dump for {}'.format(self.image_pool.pool_name))
        logging.debug(ET.tostring(self.image_pool.xml))
        logging.debug('*' * 30)
        logging.info('Cloned image to : {}'.format(target_image_name))
        cloned_image = self.image_pool.get_by_name(target_image_name)
        cloned_image.info()
        self.wait_for_state(cloned_image, IMAGE_READY)
        cloned_image.set_persistent()
        cloned_image.info()

        target_template_name = self.increase_version(template.name)
        template.clone(name=target_template_name)
        self.template_pool.info(filter=-2, range_start=-1, range_end=-1)
        cloned_template = self.template_pool.get_by_name(target_template_name)
        cloned_template.info()
        logging.info('Cloned template : {}'.format(target_template_name))

        return cloned_template, cloned_image

    def run_template_updates(self):
        logging.info(
            '*' * 5 +
            'Initializing updates for template with id {}'.format(
                self.template_id) +
            '*' * 5)
        template, image = self.clone_template()

        # change base image for template

        # Saving size to set it back after updates
        template_size = template.xml.find('TEMPLATE/DISK/SIZE')
        tmp_driver = template.xml.find('TEMPLATE/DISK/DRIVER')
        template_driver = None
        if tmp_driver is not None:
            template_driver = tmp_driver.text

        logging.info(
            'Setting {} base image to be {}'.format(
                template.name,
                image.name))
        xml_to_update = self.edit_disk(
            driver=template_driver,
            image=image.name,
            image_uname=image.uname)
        logging.info('xml_to_update:\n {}'.format(xml_to_update))
        template.update(xml_to_update, update_type=1)
        template.info()

        # Spawn VM to run updates
        vm = self.create_vm(template)

        # Connect to VM and run updates on it
        HOST = vm.xml.find('TEMPLATE/CONTEXT/ETH0_IP').text
        logging.info('*' * 30)
        logging.info('Running updates on host: {}'.format(HOST))
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        self.wait_net_port(HOST, port=22, timeout=60 * 5)
        logging.info('Connecting using {} key-file'.format(
            self.ssh_key_path))
        pk = paramiko.RSAKey.from_private_key_file(self.ssh_key_path)
        client.connect(
            hostname=HOST,
            username="root",
            pkey=pk)

        # Execute command and get its output
        __, stdout, stderr = client.exec_command('yum upgrade -y')
        while True:
            while stdout.channel.recv_ready():
                logging.info(stdout.channel.recv(1024))
            while stdout.channel.recv_stderr_ready():
                logging.info(stdout.channel.recv_stderr(1024))
            if stdout.channel.exit_status_ready():
                break
                logging.info('*' * 30)
        _, stdout, stderr = client.exec_command('sync')
        _, stdout, stderr = client.exec_command("reboot &")
        sleep(5)
        logging.info('Reboot')
        self.wait_net_port(HOST, port=22, timeout=60 * 5)

        client.close()
        sleep(5)
        self.delete_vm(vm)

        image.set_nonpersistent()
        image.info()

        # Setting size back
        if template_size is not None:
            xml_to_update = self.edit_disk(
                driver=template_driver,
                image=image.name,
                image_uname=image.uname,
                size=template_size.text)
            logging.info('xml_to_update:\n {}'.format(xml_to_update))
            template.update(xml_to_update, update_type=1)
        template.info()
        #              U  M  A
        permissions = [1, 1, 0,  # owner
                       1, 1, 0,  # group
                       1, 1, 0]  # other

        self.client.call("template.chmod", template.id, *permissions)
        self.client.call("image.chmod", image.id, *permissions)

        logging.info(
            '*' * 5 +
            'Updated template: id - {}, name - {}'.format(
                template.id, template.name) +
            '*' * 5)


def update(template_id):
    vm_template = NebulaVMTemplate.factory(
        os.environ.get(
            'KD_ONE_URL',
            'https://some.nebula.host.com:2633/RPC2'),
        os.environ['KD_ONE_USERNAME'],
        os.environ['KD_ONE_PASSWORD'],
        os.environ.get(
            'KD_ONE_PRIVATE_KEY',
            os.path.expanduser("~/.ssh/id_rsa")),
        template_id)
    vm_template.run_template_updates()


parser = argparse.ArgumentParser(
    description="Updater for OpenNebula template. Usage: \n"
                "python nebula_template_update.py <templ_id>")
parser.add_argument(
    "template_id",
    help="The id of the template to be updated",
    type=int)

if __name__ == "__main__":
    args = parser.parse_args()
    if _platform == 'linux' or _platform == 'linux2':
        update(args.template_id)
    else:
        logging.info('This script is not multiplatform. Linux only')


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

import datetime

from ..core import db
from ..utils import UPDATE_STATUSES


HOSTNAME_LENGTH = 255


class Node(db.Model):
    __tablename__ = 'nodes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    ip = db.Column(db.String(40), unique=True)
    hostname = db.Column(db.String(HOSTNAME_LENGTH), unique=True)
    kube_id = db.Column(db.Integer, db.ForeignKey('kubes.id'))
    public_interface = db.Column(db.String(15), nullable=True)
    state = db.Column(db.String(40))
    upgrade_status = db.Column(db.Text, default=UPDATE_STATUSES.applied)

    def __repr__(self):
        tpl = "<Node(hostname='{0}', ip='{1}', kube_type='{2} ({3})')>"
        return tpl.format(self.hostname, self.ip, self.kube.id, self.kube.name)

    @classmethod
    def get_by_name(cls, hostname):
        return cls.query.filter(cls.hostname == hostname).first()

    @classmethod
    def get_by_id(cls, node_id):
        return cls.query.filter(cls.id == node_id).first()

    def to_dict(self):
        return {
            "id": self.id,
            "ip": self.ip,
            "hostname": self.hostname,
            "kube_id": self.kube_id,
            "public_interface": self.public_interface,
            "state": self.state,
            "upgrade_status": self.upgrade_status
        }

    @classmethod
    def get_ip_to_hostame_map(cls):
        return {
            item.ip: item.hostname
            for item in db.session.query(cls.ip, cls.hostname)
        }

    @classmethod
    def get_all(cls):
        return cls.query.all()

    @classmethod
    def all_with_flag_query(cls, flagname, flagvalue):
        """Returns all nodes which have specified flag"""
        return db.session.query(cls).join(NodeFlag).filter(
            NodeFlag.flag_name == flagname,
            NodeFlag.flag_value == flagvalue,
            NodeFlag.deleted.is_(None))


class NodeFlag(db.Model):
    """Atrributes for nodes.
    Attribute is linked to a node by node identifier.

    """
    __tablename__ = 'node_flags'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    created = db.Column(db.DateTime, nullable=False)
    deleted = db.Column(db.DateTime, nullable=True)
    node_id = db.Column(db.Integer, db.ForeignKey(Node.id), nullable=True)
    flag_name = db.Column(db.String(63), nullable=False)
    flag_value = db.Column(db.String(127), nullable=True)

    def to_bool(self):
        if not self.flag_value:
            return False
        return self.flag_value.lower() in ('y', 'yes', 'true', '1')

    @classmethod
    def save_flag(cls, node_id, flag_name, flag_value):
        """Creates or changes a flag for a node.

        """
        node = Node.get_by_id(node_id)
        if not node:
            raise KeyError('Node not found')
        current_time = datetime.datetime.utcnow()
        flag = cls.get_by_name(node_id, flag_name)
        if flag:
            if flag.flag_value == flag_value:
                return flag
            flag.deleted = current_time
        flag = cls(
            node_id=node_id,
            created=current_time,
            flag_name=flag_name,
            flag_value=flag_value
        )
        db.session.add(flag)
        db.session.commit()
        return flag

    @classmethod
    def get_by_name(cls, node_id, name):
        """Search a flag by it's name for a node."""
        flag = cls.query.filter(
            cls.node_id == node_id, cls.flag_name == name,
            cls.deleted.is_(None)).first()
        return flag

    @classmethod
    def delete_by_name(cls, node_id, flag_name):
        cls.query(
            cls.node_id == node_id, cls.flag_name == flag_name,
            cls.deleted.is_(None)
        ).update({
            cls.deleted: datetime.datetime.utcnow()
        })
        db.session.commit()

db.Index('ix_deleted_node_id_flag_name',
         NodeFlag.deleted, NodeFlag.node_id, NodeFlag.flag_name)


class NodeFlagNames(object):
    """Known node flags which are used in different places.
    """
    # Ceph client is installed on the node
    CEPH_INSTALLED = 'ceph_installed'


class RegisteredHost(db.Model):
    __tablename__ = 'registered_hosts'
    id = db.Column(db.Integer, primary_key=True, nullable=False,
                   autoincrement=True)
    host = db.Column(db.String, nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    time_stamp = db.Column(db.DateTime, nullable=False)
    tunnel_ip = db.Column(db.String, nullable=True)

    def __repr__(self):
        return "<RegisteredHost(host='{0}', description='{1}')>".format(
            self.host, self.description)


class NodeAction(db.Model):
    __tablename__ = 'node_actions'

    host = db.Column(db.String(255), primary_key=True, nullable=False)
    command = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, primary_key=True, nullable=False)
    type = db.Column(db.String(255), nullable=False, default='')

    def __repr__(self):
        return ("<NodeAction(host='{0}', command='{1}', "
                "timestamp={2}, type='{3}')>".format(
                    self.host, self.command, repr(self.timestamp), self.type))


class LocalStorageDevices(db.Model):
    """Class stores information about block devices attached (via LVM) to
    node's local storage.
    """
    __tablename__ = 'localstorage_devices'

    node_id = db.Column(db.ForeignKey(Node.id), nullable=True,
                        primary_key=True)
    # Block device name on a node (like '/dev/sdc' or similar)
    device = db.Column(db.String(64), nullable=False, primary_key=True)
    # volume size in bytes
    size = db.Column(db.BigInteger, nullable=False)
    # AWS volume name. For generic local storage backend this field is empty.
    volume_name = db.Column(db.String(255), nullable=False, default='')

    @classmethod
    def add_device_if_not_exists(cls, node_id, device, size, volume_name=''):
        """Creates a record for a node's device if it not exists in DB."""
        exists = db.session.query(cls).filter(
            cls.node_id == node_id, cls.device == device).first()
        if exists:
            return exists
        new_record = cls(
            node_id=node_id, device=device, size=size, volume_name=volume_name
        )
        db.session.add(new_record)
        return new_record

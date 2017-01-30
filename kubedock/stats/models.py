
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

from ..core import db


class StatWrap5Min(db.Model):
    __tablename__ = 'stat_wrap_5min'
    __table_args__ = (
        db.PrimaryKeyConstraint(
            'time_window',
            'host',
            'unit_name',
            'container',
            name='window_entry'),
    )
    time_window = db.Column(db.Integer, nullable=False)
    host = db.Column(db.String(64), nullable=False)
    unit_name = db.Column(db.String(255), nullable=False, index=True)
    container = db.Column(db.String(255), nullable=False, index=True)
    cpu = db.Column(db.Float, nullable=False, default=0.0)
    memory = db.Column(db.Float, nullable=False, default=0.0)
    rxb = db.Column(db.Float, nullable=False, default=0.0)
    txb = db.Column(db.Float, nullable=False, default=0.0)
    fs_data = db.Column(db.Text, nullable=True)

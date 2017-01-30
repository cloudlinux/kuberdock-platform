
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

import traceback

from ..core import db
from kubedock.models_mixin import BaseModelMixin


class Updates(BaseModelMixin, db.Model):
    __tablename__ = 'updates'
    fname = db.Column(db.Text, primary_key=True, nullable=False)
    status = db.Column(db.Text, nullable=False)
    log = db.Column(db.Text, nullable=True)
    last_step = db.Column(db.Integer, default=0, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)

    @property
    def checkpoint(self):
        return self.last_step or 0

    @checkpoint.setter
    def checkpoint(self, val):
        self.last_step = val
        self.save()

    def print_log(self, *msg):
        if len(msg) > 0:
            m = [i.decode('utf-8') if isinstance(i, str) else unicode(i)
                 for i in msg]
            print u'\n'.join(m)
            self.log = u'\n'.join(([self.log] if self.log else []) + m) + u'\n'
            self.save()

    def capture_traceback(self, header='', footer=''):
        self.print_log(
            '{0}{1}'
            '=== Begin of captured traceback ===\n'
            '{2}'
            '=== End of captured traceback ==={3}'
            '{4}'.format(
                header,
                '\n' if header else '',
                traceback.format_exc(),
                '\n' if footer else '',
                footer
            )
        )

    def __repr__(self):
        return "<Update(fname='{0}', status='{1}')>".format(self.fname,
                                                            self.status)

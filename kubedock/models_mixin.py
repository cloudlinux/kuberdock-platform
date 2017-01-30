
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

import json
from .core import db


class BaseModelMixin(object):
    def to_dict(self, include=None, exclude=()):
        """Convert all model's columns to dict."""
        data = {field: getattr(self, field)
                for field in self.__mapper__.columns.keys()
                if field not in exclude}
        if include:
            data.update(include)
        return data

    def to_json(self, include=None, exclude=None):
        return json.dumps(self.to_dict(include=include, exclude=exclude))

    def save(self, deferred_commit=False):
        try:
            db.session.add(self)
            if not deferred_commit:
                db.session.commit()
            return self
        except Exception, e:
            print 'Operation failed with ex(%s)' % e
            db.session.rollback()
            raise e

    def delete(self):
        try:
            db.session.delete(self)
            db.session.commit()
        except Exception, e:
            print 'Operation failed with ex(%s)' % e
            raise e

    @classmethod
    def all(cls):
        return db.session.query(cls).all()

    @classmethod
    def create(cls, **kwargs):
        return cls(**kwargs)

    @classmethod
    def get_or_create(cls, **kwargs):
        obj = cls.filter_by(**kwargs).first()
        if obj:
            return obj, False
        return cls.create(**kwargs), True

    @classmethod
    def get_objects_collection(cls, to_json=False):
        data = [obj.to_dict() for obj in db.session.query(cls).all()]
        if to_json:
            return json.dumps(data)
        return data

    @classmethod
    def filter(cls, *args):
        return cls.query.filter(*args)

    @classmethod
    def filter_by(cls, **kwargs):
        return cls.query.filter_by(**kwargs)

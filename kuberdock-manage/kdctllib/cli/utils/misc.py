
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

class UnknownName(Exception):
    def __init__(self, name):
        super(UnknownName, self).__init__('Unknown name %s' % name)


def get_id_by_name(name, objs, id_field='id', name_field='name'):
    """Takes name of object and returns it's id.

    Arguments:
        name (str): Name of object
        objs (list[dict]): List of all objects
        id_field (str): Name of field that represents object's id
        name_field (str): Name of filed that represents object's name
    """
    assert isinstance(objs, list)

    filtered = (obj for obj in objs if obj[name_field] == name)
    try:
        obj = next(filtered)
    except StopIteration:
        raise UnknownName(name)

    return obj[id_field]


class ContextObj(object):
    """This object is passed as context.obj into click command."""
    kdctl = None
    executor = None
    io = None


class SimpleCommand(object):
    """Class that just redirect command to corresponding method
    of underlying executor.

    Executor must be set into `ctx.obj`.
    Implementation must be with decorator `@kdclick.pass_obj`.

    Example:
        @kdclick.group
        @kdclick.pass_ctx
        def pods(ctx):
            ctx.obj = ctx.obj.kdctl.pods


        @pods.command()
        @kdclick.argument('some-argument')
        @kdclick.pass_obj
        class List(SimpleCommand):
            pass

    So `kdctl.pods.list(some_argument=<some_argument>)` will be executed.
    """
    corresponding_method = None

    @classmethod
    def __new__(cls, command, context_obj, **kwargs):
        executor = context_obj.executor
        cls.preprocess_args(executor, kwargs)
        method_name = cls.corresponding_method or command.__name__.lower()
        m = getattr(executor, method_name)
        return m(**kwargs)

    @classmethod
    def preprocess_args(cls, executor, kwargs):
        pass


class SimpleCommandWithIdNameArgs(SimpleCommand):
    """Extension of `SimpleCommand` that allows to use name instead of id."""
    id_field = 'id'
    name_field = 'name'
    name_kwarg = 'name'

    @classmethod
    def preprocess_args(cls, executor, kwargs):
        if kwargs['id'] is None:
            kwargs['id'] = get_id_by_name(kwargs[cls.name_kwarg],
                                          executor.list()['data'],
                                          id_field=cls.id_field,
                                          name_field=cls.name_field)
        kwargs.pop(cls.name_kwarg)


class SimpleCommandWithIdNameOwnerArgs(SimpleCommandWithIdNameArgs):
    """Extension of `SimpleCommand` that allows to use name instead of id.

    Use it when you have to specify owner to get list of objects.
    """
    @classmethod
    def preprocess_args(cls, executor, kwargs):
        if kwargs['id'] is None:
            objs = executor.list(owner=kwargs['owner'])['data']
            kwargs['id'] = get_id_by_name(kwargs[cls.name_kwarg], objs,
                                          id_field=cls.id_field,
                                          name_field=cls.name_field)
        kwargs.pop(cls.name_kwarg)

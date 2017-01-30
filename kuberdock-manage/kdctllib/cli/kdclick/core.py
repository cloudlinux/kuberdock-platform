
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

import click

import access

DEFAULT_ACCESS = access.ALL


class Group(click.Group):
    def __init__(self, name=None, commands=None, **attrs):
        super(Group, self).__init__(name, commands, **attrs)

    def group(self, *args, **kwargs):
        def decorator(f):
            cmd = group(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd

        return decorator

    def command(self, *args, **kwargs):
        def decorator(f):
            cmd = command(*args, **kwargs)(f)
            self.add_command(cmd)
            return cmd

        return decorator

    def add_command(self, cmd, name=None):
        available_for = getattr(cmd, 'available_for', DEFAULT_ACCESS)
        if access.available_for(available_for):
            return super(Group, self).add_command(cmd, name)


def command(name=None, cls=None, **kwargs):
    available_for = kwargs.pop('available_for', DEFAULT_ACCESS)
    if cls is None:
        cls = click.Command

    def decorator(f):
        cmd = click.decorators._make_command(f, name, kwargs, cls)
        cmd.__doc__ = f.__doc__
        cmd.available_for = available_for
        return cmd

    return decorator


def group(name=None, **kwargs):
    kwargs.setdefault('cls', Group)
    return command(name, **kwargs)

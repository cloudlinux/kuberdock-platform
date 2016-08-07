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

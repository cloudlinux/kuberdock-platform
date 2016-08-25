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
    def __new__(cls, command, executor, **kwargs):
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

    @classmethod
    def preprocess_args(cls, executor, kwargs):
        if kwargs['id'] is None:
            kwargs['id'] = get_id_by_name(kwargs['name'],
                                          executor.list()['data'],
                                          id_field=cls.id_field,
                                          name_field=cls.name_field)
        kwargs.pop('name')


class SimpleCommandWithIdNameOwnerArgs(SimpleCommand):
    """Extension of `SimpleCommand` that allows to use name instead of id.

    Use it when you have to specify owner to get list of objects.
    """
    id_field = 'id'
    name_field = 'name'

    @classmethod
    def preprocess_args(cls, executor, kwargs):
        if kwargs['id'] is None:
            objs = executor.list(owner=kwargs['owner'])['data']
            kwargs['id'] = get_id_by_name(kwargs['name'], objs,
                                          id_field=cls.id_field,
                                          name_field=cls.name_field)
        kwargs.pop('name')

from functools import wraps

import click

import types


def data_argument(*args, **kwargs):
    """
    This decorator is combination of two decorators:
    @click.argument(<arg_name>, **kwargs)
    @click.option('-f', '--file', help='Input file.', expose_value=False)

    Only <arg_name> and <type> passed to decorated function. If -f specified,
    it read data from file and pass it to argument <arg_name>.

    Only <arg_name> and <type> passed to decorated function. If -f specified,
    it read data from file and pass it to argument <arg_name>.

    If you have questions, see examples of usages.

    Used when one can pass json data directly from command line
    or specify input json file.

    Example:
       kdctl pods restore --owner test_user '{"pod": "data"}'
       or
       kdctl pods restore --owner test_user -f pod_data.json
       
    """
    target_param_name = args[-1].replace('-', '_')

    kwargs.setdefault('type', types.json)

    def wrapper(fn):

        def c1(ctx, param, value):
            if value is not None:
                ctx.params[target_param_name] = value
            if target_param_name not in ctx.params:
                raise click.BadArgumentUsage(
                    'One of --file or %s must be specified' % target_param_name
                )
            return value

        kwargs.update(required=False, callback=c1, expose_value=False)

        d1 = click.argument(*args, **kwargs)

        def c2(ctx, param, value):
            if value is not None:
                with open(value) as f:
                    s = f.read()
                converter = kwargs['type']
                d = converter(s)
                ctx.params[target_param_name] = d
            return value

        kwargs2 = {
            'type': click.Path(exists=True, file_okay=True, dir_okay=False),
            'expose_value': False,
            'help': 'Input file',
            'callback': c2
        }
        d2 = click.option('-f', '--file', **kwargs2)
        return d2(d1(fn))

    return wrapper


def required_exactly_one_of(*arg_names):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            n = sum(1 for arg_name in arg_names
                    if kwargs.get(arg_name, None) is not None)
            if n != 1:
                raise click.BadOptionUsage('Please specify exactly one of %s '
                                           % ', '.join(arg_names))
            return fn(*args, **kwargs)

        return wrapper

    return decorator

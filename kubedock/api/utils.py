from functools import wraps

from cerberus import Validator

from kubedock.utils import all_request_params
from kubedock.validation import ValidationError


def use_args(schema, as_kwargs=False):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            params = all_request_params()
            v = Validator(schema)
            if v.validate(params):
                parsed_args = v.document

                if as_kwargs:
                    kwargs.update(parsed_args)
                    return fn(*args, **kwargs)
                else:
                    # Add parsed_args after other positional arguments
                    new_args = args + (parsed_args,)
                    return fn(*new_args, **kwargs)
            else:
                raise ValidationError(v.errors)

        return wrapper

    return decorator


def use_kwargs(schema):
    return use_args(schema, as_kwargs=True)

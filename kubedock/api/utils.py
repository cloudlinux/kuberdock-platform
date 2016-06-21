from functools import wraps

from kubedock.utils import all_request_params
from kubedock.validation import V, ValidationError


def use_args(schema, as_kwargs=False, validator_cls=V,
             **validator_kwargs):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            params = all_request_params()
            v = validator_cls(schema, **validator_kwargs)
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


def use_kwargs(schema, **kwargs):
    return use_args(schema, as_kwargs=True, **kwargs)

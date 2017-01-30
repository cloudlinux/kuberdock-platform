
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

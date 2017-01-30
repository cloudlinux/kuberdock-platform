
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

"""
Example for dns plugin. Does nothing, useful for tests, and as a reference
to write another plugins.

Dns management system expects plugin package contains:

* entry module with two functions:
    create_or_update_type_A_record, delete_type_A_record - see .entry module
    for details
* `args` variable, a list containing names of the plugin parameters.
* `is_valid_arg` function to validate plugin configuration parameters
"""

from . import entry


#: This example plugin has no parameters. In real plugin it may be user
# address of external dns system, user credentials to login there, or
# something else. To make plugin useful, for every of these parameters there
# must be a record in system settings with valid value.
ALLOWED_ARGS = []


def is_valid_arg(name, value):
    """Checks parameter valud is valid.
    :param name: parameter name, must one of entry in `args`.
    :param value: some string value
    :return: tuple of success flag and error message (None if parameter value
        is valid)
    """
    if name not in ALLOWED_ARGS:
        return False, u'Unknown parameter "{}" ({})'.format(name, value)
    return True, None

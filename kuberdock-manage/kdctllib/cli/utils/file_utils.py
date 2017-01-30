
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

import os

import yaml


def resolve_path(path, wd=None):
    if os.path.isabs(path):
        return path
    else:
        if wd is not None:
            return os.path.join(wd, path)
        else:
            return os.path.expanduser(path)


def read_yaml(filename):
    with open(filename) as f:
        d = yaml.load(f)
    return d


def save_yaml(d, filename):
    dir_name = os.path.dirname(os.path.abspath(filename))
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    with open(filename, 'w') as f:
        yaml.safe_dump(d, f, default_flow_style=False)


def chmod(filename, mode):
    os.chmod(filename, mode)


def ensure_dir(path):
    if os.path.isdir(path):
        return
    os.makedirs(path)

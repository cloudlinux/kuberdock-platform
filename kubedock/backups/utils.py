
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

import urlparse


def join_url(base_url, path):
    """Joins base url and path removing extra slashes.
    Removes trailing slashes. Joins queries.
    E.g.: See unit tests.
    :param base_url: Base url.
    :param path: Path.
    :return: Joined url.
    """
    # Example of usages see in unittests
    base_url = urlparse.urlsplit(base_url, allow_fragments=False)
    path = urlparse.urlsplit(path, allow_fragments=False)
    full_path = _join_paths(base_url.path, path.path)
    full_query = _join_queries(base_url.query, path.query)
    return urlparse.urlunsplit(
        (base_url.scheme, base_url.netloc, full_path, full_query,
         base_url.fragment))


def _join_paths(*parts):
    rv = ''
    for part in parts:
        x = part.strip('/')
        if x:
            rv += '/' + x
    return rv


def _join_queries(*parts):
    non_empty_parts = (p for p in parts if p)
    return '&'.join(non_empty_parts)

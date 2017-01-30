
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

import json

import kdclick


class IO(object):
    def __init__(self, json_only):
        self.json_only = json_only

    def out_text(self, text, **kwargs):
        """Print text. If `self.json_only` == True,
        then text will not be printed.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.echo()`.
        """
        if not self.json_only:
            kdclick.echo(text, **kwargs)

    def out_json(self, message, **kwargs):
        """Print message as json.
        :param message: Message to be printed.
        :param kwargs: Is passed to `kdclick.echo()`.
        """
        message = json.dumps(message, indent=4, sort_keys=True,
                             ensure_ascii=False)
        kdclick.echo(message, **kwargs)

    def confirm(self, text, **kwargs):
        """Prompts for confirmation (yes/no question).
        Parameter `self.json_only` must be set to False, otherwise
        `kdclick.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.confirm()`.
        :return: True or False.
        """
        if self.json_only:
            raise kdclick.UsageError(
                'Cannot perform confirmation in json-only mode')
        return kdclick.confirm(text, **kwargs)

    def prompt(self, text, **kwargs):
        """Prompts a user for input.
        Parameter `self.json_only` must be set to False, otherwise
        `kdclick.UsageError` will be raised.
        :param text: Text to be prompted.
        :param kwargs: Is passed to `kdclick.prompt()`.
        :return: User input.
        """
        if self.json_only:
            raise kdclick.UsageError(
                'Cannot perform user input in json-only mode')
        return kdclick.prompt(text, **kwargs)


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

from blinker import Namespace

users_signals = Namespace()
user_logged_in = users_signals.signal('user_logged_in')
user_logged_out = users_signals.signal('user_logged_out')
user_logged_in_by_another = users_signals.signal('user_logged_in_by_another')
user_logged_out_by_another = users_signals.signal('user_logged_out_by_another')
user_get_all_settings = users_signals.signal('user_get_all_settings')
user_get_setting = users_signals.signal('user_get_setting')
user_set_setting = users_signals.signal('user_set_setting')

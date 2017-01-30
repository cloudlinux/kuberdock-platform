
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

from backup_node_merge import group_by_timestamp, MergeError
from tests_integration.lib.integration_test_utils import assert_raises, assert_eq


def test_grouping():
    data = ["local_pv_backup_2016-09-22T05:01:00.0000",
            "local_pv_backup_2016-09-22T05:02:00.0000",
            "local_pv_backup_2016-09-22T07:01:00.0000",
            "local_pv_backup_2016-09-22T07:02:00.0000",
            "local_pv_backup_2016-09-22T09:01:00.0000",
            "local_pv_backup_2016-09-22T09:02:00.0000",
            "local_pv_backup_2016-09-22T11:01:00.0000",
            "local_pv_backup_2016-09-22T11:02:00.0000",
            ]
    g1, g2, g3, g4 = list(group_by_timestamp(data, 3600))
    assert g1 == ['local_pv_backup_2016-09-22T05:01:00.0000',
                  'local_pv_backup_2016-09-22T05:02:00.0000']
    assert g2 == ['local_pv_backup_2016-09-22T07:01:00.0000',
                  'local_pv_backup_2016-09-22T07:02:00.0000']
    assert g3 == ['local_pv_backup_2016-09-22T09:01:00.0000',
                  'local_pv_backup_2016-09-22T09:02:00.0000']
    assert g4 == ['local_pv_backup_2016-09-22T11:01:00.0000',
                  'local_pv_backup_2016-09-22T11:02:00.0000']


def test_grouping_raises():
    data = ["local_pv_backup",
            "local_pv_backup_2016-09-22T05:02:00.0000"]
    with assert_raises(MergeError):
        list(group_by_timestamp(data, 3600))


def test_grouping_skipping_raises():
    data = ["local_pv_backup",
            "local_pv_backup_2016-09-22T05:02:00.0000"]
    g1, = list(group_by_timestamp(data, 3600, skip_errors=True))
    assert g1 == ['local_pv_backup_2016-09-22T05:02:00.0000']

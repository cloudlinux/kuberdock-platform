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

import contextlib
import os
import shutil
import tempfile

from backup_node_merge import MergeError, do_merge, group_by_timestamp
from tests_integration.lib.utils import assert_raises


@contextlib.contextmanager
def make_temp_directory():
    temp_dir = tempfile.mkdtemp()
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir)


def make_backup_directory(dst):
    snaps = [os.path.join(dst, snap) for snap in [
        'local_pv_backup_2016-09-22T05:01:00.0000',
        'local_pv_backup_2016-09-22T05:02:00.0000',
        'local_pv_backup_2016-09-22T07:01:00.0000',
        'local_pv_backup_2016-09-22T07:02:00.0000'
    ]]

    for idx, snap in enumerate(snaps, 1):
        location = os.path.join(dst, snap)
        os.mkdir(location)
        open(os.path.join(location, "disk{}.zip".format(idx)), 'a').close()

    return snaps


def test_grouping():
    """
    """
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
    with assert_raises(MergeError, 'has unrecognized name format'):
        list(group_by_timestamp(data, 3600))


def test_grouping_skipping_raises():
    data = ["local_pv_backup",
            "local_pv_backup_2016-09-22T05:02:00.0000"]
    g1, = list(group_by_timestamp(data, 3600, skip_errors=True))
    assert g1 == ['local_pv_backup_2016-09-22T05:02:00.0000']


def test_merge():
    with make_temp_directory() as backups:
        snaps = make_backup_directory(backups)
        do_merge(backups, precision=1, dry_run=False,
                 include_latest=False, skip_errors=False)

        first, second, third, fourth = snaps
        # All files from first group were merged into first folder
        assert os.listdir(first) == ["disk1.zip", "disk2.zip"]
        # Second folder was deleted
        assert not os.path.exists(second)
        # Files from second group was not affected
        assert os.listdir(third) == ["disk3.zip"]
        assert os.listdir(fourth) == ["disk4.zip"]


def test_marge_latest_include():
    with make_temp_directory() as backups:
        first, second, third, fourth = make_backup_directory(backups)
        do_merge(backups, precision=1, dry_run=False,
                 include_latest=True, skip_errors=False)

        # All files from first group here merged into first folder
        assert os.listdir(first) == ["disk1.zip", "disk2.zip"]
        # Second folder was deleted
        assert not os.path.exists(second)

        # All files from second group were merged into first folder
        assert os.listdir(third) == ["disk3.zip", "disk4.zip"]
        # Second folder was deleted
        assert not os.path.exists(fourth)


def test_merge_dry_run():
    with make_temp_directory() as backups:
        snaps = make_backup_directory(backups)
        do_merge(backups, precision=1, dry_run=True,
                 include_latest=False, skip_errors=False)
        first, second, third, fourth = snaps
        # All files stiil on same places
        assert os.listdir(first) == ["disk1.zip"]
        assert os.listdir(second) == ["disk2.zip"]
        assert os.listdir(third) == ["disk3.zip"]
        assert os.listdir(fourth) == ["disk4.zip"]


def test_merge_with_override():
    with make_temp_directory() as backups:
        first, second, third, fourth = make_backup_directory(backups)
        os.rename(
            os.path.join(second, "disk2.zip"),
            os.path.join(second, "disk1.zip"),
        )
        with assert_raises(MergeError, 'contains overlapping files'):
            do_merge(backups, precision=1, dry_run=True,
                     include_latest=False, skip_errors=False)


def test_merge_with_big_precision():
    with make_temp_directory() as backups:
        first, second, third, fourth = make_backup_directory(backups)
        do_merge(backups, precision=5, dry_run=False,
                 include_latest=True, skip_errors=False)
        assert os.listdir(first) == ["disk1.zip", "disk2.zip",
                                     "disk3.zip", "disk4.zip"]


def test_merge_with_wrong_precision():
    with make_temp_directory() as backups:
        first, second, third, fourth = make_backup_directory(backups)
        do_merge(backups, precision=0.01, dry_run=False,
                 include_latest=True, skip_errors=False)
        assert os.listdir(first) == ["disk1.zip"]
        assert os.listdir(second) == ["disk2.zip"]
        assert os.listdir(third) == ["disk3.zip"]
        assert os.listdir(fourth) == ["disk4.zip"]


def test_merge_empty():
    with make_temp_directory() as backups:
        with assert_raises(MergeError, 'Nothing found.'):
            do_merge(backups, precision=1, dry_run=False,
                     include_latest=False, skip_errors=False)

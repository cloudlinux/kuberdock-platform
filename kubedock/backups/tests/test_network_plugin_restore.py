import os
import tarfile

import pytest
import responses
from requests.exceptions import RequestException

from node_network_plugin import VolumeRestoreException, LocalStorage, \
    VolumeManager, VolumeSpec
import node_network_plugin

volume_manager = VolumeManager()


@pytest.fixture
def backups_location():
    """Base URL for where to look for volume backups."""
    return 'http://1.2.3.4/subfolder'


@pytest.fixture
def volume_spec(backups_location, storage_dir):
    backup_url = backups_location + '/3/test_nginx.tar.gz'
    path = os.path.join(storage_dir.strpath, '3', 'test_nginx_2')
    return VolumeSpec(path=path, size='1g', name='test_nginx',
                      backup_url=backup_url)


@pytest.fixture
def backup_archive(tmpdir):
    """
    Sample backup archive which is downloaded from some server
    """
    archive_dir = tmpdir.mkdir('backup')

    archive = tmpdir.join('test.tar.gz')
    with tarfile.open(archive.strpath, 'w:gz') as a:
        f = archive_dir.join('some file.txt')
        f.write('some content')
        a.add(f.strpath)
    return archive.read()


@pytest.fixture
def storage_dir(tmpdir):
    """
    Represents a persistent storage directory
    """
    return tmpdir.mkdir('kuberdock_persistent_storage')


@pytest.fixture
def pod_spec(tmpdir, volume_spec):
    pod_spec_file = os.path.join(os.path.dirname(__file__), 'pod_spec.json')
    data = open(pod_spec_file).read()
    data = data.replace('{BACKUP_URL}', volume_spec.backup_url)
    data = data.replace("{STORAGE}", volume_spec.path)
    data = data.replace("{NAME}", volume_spec.name)
    spec = tmpdir.join('fe62065a-70d9-427c-8281-6d5e748d3e47-8jdfx-spec')
    spec.write(data)
    return spec


def mock_remote_storage(url, status=200, body=None):
    responses.add(responses.GET, url, status=status, body=body)


@responses.activate
def test_restore_volume_correctly_downloads_and_unpacks_archive(
        storage_dir, volume_spec, backup_archive):
    mock_remote_storage(volume_spec.backup_url, status=200,
                        body=backup_archive)

    volume_manager.restore_if_needed(volume_spec)
    assert len(storage_dir.listdir()) > 0


@responses.activate
def test_restore_volume_raises_if_archive_is_broken(
        storage_dir, volume_spec):
    mock_remote_storage(volume_spec.backup_url, status=200,
                        body='bad response')

    with pytest.raises(VolumeRestoreException):
        volume_manager.restore_if_needed(volume_spec)

    assert storage_dir.listdir() == []


@responses.activate
def test_restore_volume_raises_if_bad_http_code_is_returned(
        storage_dir, volume_spec):
    mock_remote_storage(volume_spec.backup_url, status=404)

    with pytest.raises(VolumeRestoreException):
        volume_manager.restore_if_needed(volume_spec)

    assert storage_dir.listdir() == []


@responses.activate
def test_restore_volume_raises_if_http_connection_breaks(
        storage_dir, volume_spec):
    exception = RequestException('Something went wrong')
    mock_remote_storage(volume_spec.backup_url, body=exception)

    with pytest.raises(VolumeRestoreException):
        volume_manager.restore_if_needed(volume_spec)

    assert storage_dir.listdir() == []


@responses.activate
def test_local_storage_init_successfully_unpacks_archive(
        storage_dir, volume_spec, mocker, pod_spec, backup_archive):
    mocker.patch.object(node_network_plugin, '_run_storage_manage_command')

    mock_remote_storage(volume_spec.backup_url, status=200,
                        body=backup_archive)

    node_network_plugin._run_storage_manage_command.return_value = (True, None)
    LocalStorage.init(pod_spec.strpath)
    node_network_plugin._run_storage_manage_command.assert_called_once_with(
        ['create-volume', '--path', volume_spec.path, '--quota',
         volume_spec.size.replace('g', '')]
    )


@responses.activate
def test_local_storage_init_removes_trash_if_restore_fails(
        volume_spec, mocker, pod_spec):
    mock_remote_storage(volume_spec.backup_url, status=200, body='trahs')
    mocker.patch.object(node_network_plugin, '_run_storage_manage_command')
    node_network_plugin._run_storage_manage_command.return_value = (True, None)

    with pytest.raises(VolumeRestoreException):
        LocalStorage.init(pod_spec.strpath)

    node_network_plugin._run_storage_manage_command.assert_any_call(
        ['create-volume', '--path', volume_spec.path, '--quota',
         volume_spec.size.replace('g', '')]
    )
    node_network_plugin._run_storage_manage_command.assert_called_with(
        ['remove-volume', '--path', volume_spec.path]
    )


@responses.activate
def test_local_storage_init_remove_storage_if_failed_to_download_backup(
        volume_spec, mocker, pod_spec):
    mock_remote_storage(volume_spec.backup_url, status=404)
    mocker.patch.object(node_network_plugin, '_run_storage_manage_command')
    node_network_plugin._run_storage_manage_command.return_value = (True, None)

    with pytest.raises(VolumeRestoreException):
        LocalStorage.init(pod_spec.strpath)

    node_network_plugin._run_storage_manage_command.assert_any_call(
        ['create-volume', '--path', volume_spec.path, '--quota',
         volume_spec.size.replace('g', '')]
    )
    node_network_plugin._run_storage_manage_command.assert_called_with(
        ['remove-volume', '--path', volume_spec.path]
    )

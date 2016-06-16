import os
import tarfile

import pytest
import responses
from requests.exceptions import RequestException

from node_network_plugin import VolumeRestoreException, LocalStorage, Volume


@pytest.fixture
def volumes_dir_url():
    """
    Base URL for where to look for volume backups
    """
    return 'http://1.2.3.4/subfolder'


@pytest.fixture
def volume(volumes_dir_url, storage_dir):
    """
    Helper function which contains information about a volume
    """
    volume_url = volumes_dir_url + '/backups/3/test_nginx.tar.gz'
    path = os.path.join(storage_dir.strpath, '3', 'test_nginx_2')

    return {
        'url': volume_url, 'user_id': '3', 'name': 'test_nginx', 'path': path,
        'size': '1g'
    }


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
def pod_spec(tmpdir, volume, volumes_dir_url):
    data = open('kubedock/pod_spec.json').read()
    data = data.replace('{URL}', volumes_dir_url)
    data = data.replace("{STORAGE}", volume['path'])
    data = data.replace("{NAME}", volume['name'])
    spec = tmpdir.join('fe62065a-70d9-427c-8281-6d5e748d3e47-8jdfx-spec')
    spec.write(data)
    return spec


def mock_remote_storage(url, status=200, body=None):
    responses.add(responses.GET, url, status=status, body=body)


@responses.activate
def test_restore_volume_correctly_downloads_and_unpacks_archive(
        volumes_dir_url, storage_dir, volume, backup_archive):
    mock_remote_storage(volume['url'], status=200, body=backup_archive)

    v = Volume(volume['path'], volume['size'], volume['name'])
    v.restore(volumes_dir_url, volume['user_id'])
    assert len(storage_dir.listdir()) > 0


@responses.activate
def test_restore_volume_raises_if_archive_is_broken(
        volumes_dir_url, storage_dir, volume):
    mock_remote_storage(volume['url'], status=200, body='bad response')

    with pytest.raises(VolumeRestoreException):
        v = Volume(volume['path'], volume['size'], volume['name'])
        v.restore(volumes_dir_url, volume['user_id'])

    assert storage_dir.listdir() == []


@responses.activate
def test_restore_volume_raises_if_bad_http_code_is_returned(
        volumes_dir_url, storage_dir, volume):
    mock_remote_storage(volume['url'], status=404)

    with pytest.raises(VolumeRestoreException):
        v = Volume(volume['path'], volume['size'], volume['name'])
        v.restore(volumes_dir_url, volume['user_id'])

    assert storage_dir.listdir() == []


@responses.activate
def test_restore_volume_raises_if_http_connection_breaks(
        volumes_dir_url, storage_dir, volume):
    exception = RequestException('Something went wrong')
    mock_remote_storage(volume['url'], body=exception)

    with pytest.raises(VolumeRestoreException):
        v = Volume(volume['path'], volume['size'], volume['name'])
        v.restore(volumes_dir_url, volume['user_id'])

    assert storage_dir.listdir() == []


@responses.activate
def test_local_storage_init_successfully_unpacks_archive(
        storage_dir, volume, mocker, pod_spec, backup_archive):
    mocker.patch('subprocess.call')
    mock_remote_storage(volume['url'], status=200, body=backup_archive)

    LocalStorage.init(pod_spec.strpath)

    assert storage_dir.listdir()


@responses.activate
def test_local_storage_init_removes_trash_if_restore_fails(
        volume, mocker, pod_spec):
    mocker.patch('subprocess.call')
    mock_remote_storage(volume['url'], status=200, body='trahs')

    with pytest.raises(VolumeRestoreException):
        LocalStorage.init(pod_spec.strpath)

    assert not os.path.exists(volume['path'])


@responses.activate
def test_local_storage_init_remove_storage_if_failed_to_download_backup(
        volume, mocker, pod_spec):
    mocker.patch('subprocess.call')
    mock_remote_storage(volume['url'], status=404)

    with pytest.raises(VolumeRestoreException):
        LocalStorage.init(pod_spec.strpath)

    assert not os.path.exists(volume['path'])

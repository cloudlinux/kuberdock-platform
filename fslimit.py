"""
Usage: fslimit.py containers|storage [name=limit ...]

Examples:
fslimit.py containers a00750a46fbb3c5bd512c790031dca02ef87359ae3cb54f70bdb2a2f6e0f66a9=1g
fslimit.py storage 63ce0925-1b11-4688-98cb-f5a934030d4b=5g ca3a36ed-fc85-4fdf-ae29-f777f0923089=10g
"""

import glob
import os
import re
import subprocess
import sys


OVERLAY = '/var/lib/docker/overlay'
PROJECTS = '/etc/projects'
PROJID = '/etc/projid'
PROJECT_PATTERN = re.compile('^(?P<id>\d+):(?P<path>.+)$')
PROJID_PATTERN = re.compile('^(?P<name>.+):(?P<id>\d+)$')
STORAGE = '/var/lib/kuberdock/storage'


def _containers():
    containers = {}
    target_path = os.path.join(OVERLAY, '*', 'upper')
    for target in glob.glob(target_path):
        container_path = os.path.dirname(target)
        if not container_path.endswith('-init'):
            container_name = os.path.basename(container_path)
            containers[container_name] = container_path
    return containers


def _exit(message, code, usage=False):
    print message
    if usage:
        print __doc__
    sys.exit(code)


def _fs():
    mounts = {}
    with open('/proc/mounts') as mounts_file:
        for mount in mounts_file.readlines():
            device, mount_point, file_system, _options = mount.split()[:4]
            mounts[mount_point] = {
                'device': device,
                'mount_point': mount_point,
                'file_system': file_system,
                'options': _options.split(','),
            }
    return mounts


def _limits(parent):
    limits = {}
    for limit in sys.argv[2:]:
        name, _, value = limit.partition('=')
        path = os.path.join(parent, name)
        limits[name] = {'limit': value, 'path': path}
    return limits


def _mount(path):
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


def _storage():
    storage = {}
    target_path = os.path.join(STORAGE, '*')
    for storage_path in glob.glob(target_path):
        storage_name = os.path.basename(storage_path)
        storage[storage_name] = storage_path
    return storage


def _target():
    if len(sys.argv) < 2:
        _exit('No target specified', 3, usage=True)
    target = sys.argv[1]
    if target == 'containers':
        return OVERLAY, _containers
    if target == 'storage':
        return STORAGE, _storage
    _exit('Unknown target', 4, usage=True)


def check_xfs(fs):
    fs_type = fs['file_system']
    if fs_type != 'xfs':
        _exit('Only XFS supported as backing filesystem', 1)


def check_prjquota(fs):
    if 'prjquota' not in fs['options']:
        _exit('Enable project quota for {0}'.format(fs['device']), 2)


def fslimit(fs, parent, dirs):
    delete = set()
    max_id = 0
    projects = set()
    projects_lines = []
    projid_lines = []
    if os.path.exists(PROJECTS) and os.path.exists(PROJID):
        with open(PROJECTS) as projects_file:
            for project in projects_file.read().splitlines():
                project_match = PROJECT_PATTERN.match(project)
                if project_match:
                    project_dict = project_match.groupdict()
                    id_ = int(project_dict['id'])
                    path = project_dict['path']
                    if path.startswith(parent):
                        name = os.path.basename(path)
                        if name not in dirs:
                            delete.add(id_)
                            continue
                        projects.add(name)
                    max_id = max([max_id, id_])
                projects_lines.append(project)
        with open(PROJID) as projid_file:
            for projid in projid_file.read().splitlines():
                projid_match = PROJID_PATTERN.match(projid)
                if projid_match:
                    projid_dict = projid_match.groupdict()
                    id_ = int(projid_dict['id'])
                    if id_ in delete:
                        continue
                    max_id = max([max_id, id_])
                projid_lines.append(projid)
    new = _limits(parent)
    for name, data in new.items():
        if name not in projects:
            max_id += 1
            projects_lines.append('{0}:{1}'.format(max_id, data['path']))
            projid_lines.append('{0}:{1}'.format(name, max_id))
    with open(PROJECTS, 'w') as projects_file:
        projects_file.writelines(l + os.linesep for l in projects_lines)
    with open(PROJID, 'w') as projid_file:
        projid_file.writelines(l + os.linesep for l in projid_lines)
    for name, data in new.items():
        project = 'project -s {0}'.format(name)
        limit = 'limit -p bsoft={0} bhard={0} {1}'.format(data['limit'], name)
        for c in project, limit:
            subprocess.call(['xfs_quota', '-x', '-c', c, fs['mount_point']])


if __name__ == '__main__':
    _parent, _dirs = _target()
    fs_ = _fs()[_mount(_parent)]
    check_xfs(fs_)
    check_prjquota(fs_)
    fslimit(fs_, _parent, _dirs())

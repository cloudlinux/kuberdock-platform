"""
Usage: fslimit.py containers|storage [name=limit ...]

Examples:
fslimit.py containers a00750a46fbb3c5bd512c790031dca02ef87359ae3cb54f70bdb2a2f6e0f66a9=1g
fslimit.py storage /var/lib/kuberdock/storage/23/mydrive1=5g
fslimit.py storage mydrive1_23=3g
"""

import glob
import os
import re
import subprocess
import sys


OVERLAY = '/var/lib/docker/overlay'
PROJECTS = '/etc/projects'
PROJID = '/etc/projid'
PROJECT_PATTERN = re.compile(r'^(?P<id>\d+):(?P<path>.+)$')
PROJID_PATTERN = re.compile(r'^(?P<name>.+):(?P<id>\d+)$')
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
        # Use given names as paths if it represent an absolute path. Otherwise
        # use it as subdir for the parent dir.
        if name.startswith('/'):
            path = name
        else:
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
        # we expect here directories like <STORAGE>/<user id>/<user storage>
        if not os.path.isdir(storage_path):
            continue
        subdir = os.path.basename(storage_path)
        try:
            int(subdir)
        except (TypeError, ValueError):
            continue
        user_storage_parent = os.path.join(storage_path, '*')
        for lstorage in glob.glob(user_storage_parent):
            storage[lstorage] = lstorage
    return storage


FSLIMIT_TARGETS = {
    'containers': (OVERLAY, _containers),
    'storage': (STORAGE, _storage,),
}


def _target():
    """Returns tuple of Parent directory, method for getting subdirs and
    flag which determine the way of working with paths - use absolute
    """
    if len(sys.argv) < 2:
        _exit('No target specified', 3, usage=True)
    target = sys.argv[1]
    if target not in FSLIMIT_TARGETS:
        _exit('Unknown target', 4, usage=True)
    return target


def check_xfs(fs):
    fs_type = fs['file_system']
    if fs_type != 'xfs':
        _exit('Only XFS supported as backing filesystem', 1)


def check_prjquota(fs):
    if 'prjquota' not in fs['options']:
        _exit('Enable project quota for {0}'.format(fs['device']), 2)


def fslimit(fs, parent, dirs, abspath=False):
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
                        if abspath:
                            name = path
                        else:
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
    for name, data in new.iteritems():
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

    target_ = _target()
    parent_, get_dirs = FSLIMIT_TARGETS[target_]

    use_abspath = False
    if target_ == 'storage':
        use_abspath = True
    fs_ = _fs()[_mount(parent_)]
    check_xfs(fs_)
    check_prjquota(fs_)
    fslimit(fs_, parent_, get_dirs(), abspath=use_abspath)

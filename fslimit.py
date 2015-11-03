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


def _containers():
    containers = {}
    target_path = os.path.join(OVERLAY, '*', 'upper')
    for target in glob.glob(target_path):
        container_path = os.path.dirname(target)
        if not container_path.endswith('-init'):
            container_name = os.path.basename(container_path)
            containers[container_name] = container_path
    return containers


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


def _limits():
    limits = {}
    for limit in sys.argv[1:]:
        name, _, value = limit.partition('=')
        path = os.path.join(OVERLAY, name)
        limits[name] = {'limit': value, 'path': path}
    return limits


def _mount(path=None):
    if path is None:
        path = OVERLAY
    while not os.path.ismount(path):
        path = os.path.dirname(path)
    return path


fs = _fs()[_mount()]


def check_xfs():
    fs_type = fs['file_system']
    if fs_type != 'xfs':
        print 'Only XFS supported as backing filesystem'
        sys.exit(1)


def check_prjquota():
    if 'prjquota' not in fs['options']:
        print 'Enable project quota for {0}'.format(fs['device'])
        sys.exit(2)


def fslimit():
    containers = _containers()
    delete = set()
    max_id = 0
    projects = set()
    projects_lines = []
    projid_lines = []
    if os.path.exists(PROJECTS) and os.path.exists(PROJID):
        with open(PROJECTS) as projects_file:
            for project in projects_file.read().splitlines():
                project_match = re.match(PROJECT_PATTERN, project)
                if project_match:
                    project_dict = project_match.groupdict()
                    id_ = int(project_dict['id'])
                    path = project_dict['path']
                    if path.startswith(OVERLAY):
                        name = os.path.basename(path)
                        if name not in containers:
                            delete.add(id_)
                            continue
                        projects.add(name)
                    max_id = max([max_id, id_])
                projects_lines.append(project)
        with open(PROJID) as projid_file:
            for projid in projid_file.read().splitlines():
                projid_match = re.match(PROJID_PATTERN, projid)
                if projid_match:
                    projid_dict = projid_match.groupdict()
                    id_ = int(projid_dict['id'])
                    if id_ in delete:
                        continue
                    max_id = max([max_id, id_])
                projid_lines.append(projid)
    new = _limits()
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
    check_xfs()
    check_prjquota()
    fslimit()

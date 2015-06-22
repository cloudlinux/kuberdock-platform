import json
from os import path
import re
from shlex import shlex


from_pattern = re.compile(
    '^(?P<full>(?P<name>[^\s:@]+?)'
    '(?:(?::(?P<tag>\S*))|'
    '(?:@(?P<digest>(?:(?P<algorithm>\S*):)?(?P<hash>\S*))))?)$'
)


def _process_cmd(data):
    try:
        cmd = json.loads(data)
        if not isinstance(cmd, list):
            raise ValueError
    except ValueError:
        cmd = ['/usr/sh', '-c', data]
    return cmd


def _shlex(data):
    return ''.join(shlex(data, posix=True))


class DockerfileParser(object):

    def __init__(self, data=None):
        self._dispatcher = {
            'FROM': self._from,
            'CMD': self._cmd,
            'EXPOSE': self._expose,
            'ENV': self._env,
            'ENTRYPOINT': self._entry_point,
            'VOLUME': self._volume,
            'WORKDIR': self._workdir,
            'ONBUILD': self._onbuild,
        }
        self._lines = []
        self._build = None
        self.parent = {}
        self.command = []
        self.ports = set()
        self.envs = set()
        self.entry_point = []
        self.volumes = set()
        self.workging_dir = ''

        if data is not None:
            for line in data.splitlines():
                self.append(line)

    def _nop(self, data):
        pass

    def _parse(self, line):
        instruction, _, data = line.partition(' ')
        data = data.strip()
        self._dispatcher.get(instruction, self._nop)(data)

    def _from(self, data):
        self.parent = from_pattern.match(data).groupdict()

    def _cmd(self, data):
        self.command = _process_cmd(data)


    def _expose(self, data):
        for port_raw in data.split():
            port_raw = _shlex(port_raw)
            number, _, protocol = port_raw.partition('/')
            if protocol not in ('', 'tcp', 'udp'):
                raise ValueError('Invalid protocol ({0})'.format(protocol))
            if not protocol:
                protocol = 'tcp'
            protocol = protocol.lower()
            if '-' in number:
                start, end = map(int, number.split('-'))
                for n in range(start, end + 1):
                    self.ports.add((n, protocol))
            else:
                self.ports.add((number, protocol))

    def _env(self, data):
        name, _, value = data.partition(' ')
        if '=' in name:
            sh_list = list(shlex(data, posix=True))
            sh_triplets = [sh_list[x:x+3] for x in range(0, len(sh_list), 3)]
            for sh_triplet in sh_triplets:
                try:
                    name, equal_sign, value = sh_triplet
                    if equal_sign != '=':
                        raise ValueError
                except ValueError:
                    raise ValueError('Error parsing "{0}"'.format(data))
                self.envs.add((name, value))
        else:
            self.envs.add((name, value))

    def _entry_point(self, data):
        self.entry_point = _process_cmd(data)

    def _volume(self, data):
        try:
            volumes = json.loads(data)
            if not isinstance(volumes, list):
                raise ValueError
        except ValueError:
            volumes = data.split()
        self.volumes.update(map(lambda x: _shlex(x.strip('\\')), volumes))

    def _workdir(self, data):
        if not self.workging_dir:
            self.workging_dir = '/'
        working_dir = _shlex(data)
        self.workging_dir = path.join(self.workging_dir, working_dir)

    def _onbuild(self, data):
        if not self._build:
            self._build = DockerfileParser()
        self._build.append(data)

    def append(self, line):
        line = line.strip()
        if line.startswith('#') or not line:
            return
        if line.endswith('\\'):
            line = line[:-1].strip()
            self._lines.append(line)
            return
        if self._lines:
            self._lines.append(line)
            line = ' '.join(self._lines)
            self._lines = []
        self._parse(line)

    def get(self):
        command = []
        command.extend(self.entry_point)
        command.extend(self.command)
        result = {
            'parent': self.parent,
            'command': command,
            'workingDir': self.workging_dir,
            'ports': list(self.ports),
            'volumeMounts': list(self.volumes),
            'env': list(self.envs),
        }
        if self._build:
            result['onbuild'] = self._build.get()
            result['onbuild'].pop('parent', None)
        return result

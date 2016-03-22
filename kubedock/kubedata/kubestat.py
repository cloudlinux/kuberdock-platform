from influxdb import client
from .. import settings
from collections import OrderedDict
import time
from ..core import db
from ..pods import Pod
from ..users import User
from ..utils import from_binunit
import socket
import re
import requests
from influxdb.client import InfluxDBClientError

from ..utils import get_api_url


class KubeUnitResolver(object):
    def __init__(self):
        self._ids = []
        self._containers = {}

    def by_unit(self, uuid):
        unit = db.session.query(Pod).get(uuid)
        if unit is None:
            return self._containers
        self._ids.append(unit.id)
        self._get_containers()
        return self._containers

    def all(self):
        data = db.session.query(Pod).all()
        self._ids.extend([i.id for i in data])
        self._get_containers()
        return self._containers

    def by_user(self, username=None):
        data = db.session.query(Pod).join(Pod.owner).filter_by(
            username=User.username).values(Pod.id)
        self._ids.extend([i[0] for i in data])
        self._get_containers()
        return self._containers

    def __getattr__(self, name):
        if name == '_data':
            url = get_api_url('pods', namespace=False)
            r = requests.get(url)
            return r.json()
        raise AttributeError("No such attribute: %s" % (name,))

    def _get_containers(self):
        if 'items' not in self._data:
            return
        ip_patt = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
        for item in self._data['items']:
            try:
                if item['metadata']['labels']['kuberdock-pod-uid'] not in self._ids:
                    continue
                host = item['spec']['nodeName']
                if ip_patt.match(host):
                    host = socket.gethostbyaddr(host)[0]
                if host not in self._containers:
                    self._containers[host] = []
                for c in item['spec']['containers']:
                    self._containers[host].append((
                        c['name'], item['metadata']['name'],
                        item['metadata']['labels']['kuberdock-pod-uid']
                    ))
            except KeyError:
                continue
            except socket.herror:
                pass


class KubeStat(object):
    SELECT_COLUMNS = [
        'cpu_cumulative_usage',
        'memory_usage',
        'rx_bytes',
        'rx_errors',
        'tx_bytes',
        'tx_errors',
        'container_name',
        'machine',
        'fs_device',
        'fs_limit',
        'fs_usage']

    TIME_FORMATS = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S']

    def __init__(self, start=None, end=None, resolution=60):

        self._folded = OrderedDict()
        self._unfolded = []
        self._wanted_map = {}
        self._resolution = resolution
        self._nodes = self._get_nodes_info()
        self._cumulatives = {'cpu_cumulative_usage':'cpu', 'rx_bytes': 'rxb', 'tx_bytes': 'txb'}
        start_point = int(time.time() - 3600) if start is None else self.timestamp(start)
        self._startcond = "time > %ds" % (start_point,)

        end_point = None if end is None else self.timestamp(end)
        self._endcond = '' if end_point is None else "time < %ds" % (end_point,)

        self._windows = self._make_windows(start_point, end_point)
        colstr = ', '.join(['%s' % (c,) for c in self.SELECT_COLUMNS])
        conds = filter(None, [self._startcond, self._endcond])
        condstr = ' where %s' % (' and '.join(conds),) if len(conds) != 0 else ''
        self.query_str = 'select %s from %s%s;' % (colstr, settings.INFLUXDB_TABLE, condstr)

    def _make_query(self):
        conn = client.InfluxDBClient(
            settings.INFLUXDB_HOST,
            settings.INFLUXDB_PORT,
            settings.INFLUXDB_USER,
            settings.INFLUXDB_PASSWORD,
            settings.INFLUXDB_DATABASE)
        try:
            self._data = conn.query(self.query_str)[0]
        except IndexError:
            self._data = {'points': [], 'columns': []}

    @staticmethod
    def _get_nodes_info():
        data = {}
        url = get_api_url('nodes', namespace=False)
        r=requests.get(url)

        try:
            rv = r.json()
        except (TypeError, ValueError):
            return {}

        for node in rv.get('items', []):
            name = node.get('metadata', {}).get('name')
            if name is None:
                continue
            cpu = node.get('status', {}).get('capacity', {}).get('cpu', '1')
            mem = node.get('status', {}).get('capacity', {}).get('memory',
                                                                 '1048576Ki')
            data[name] = {'cores': int(cpu)/8,
                          'memory': from_binunit(mem, 'MiB', rtype=int)/4}
        return data

    def _make_windows(self, start_point, end_point):
        if end_point is None:
            end_point = int(time.time())
        start_point = start_point - start_point % self._resolution
        modulo = end_point % self._resolution
        if modulo != 0:
            end_point = (end_point - modulo) + self._resolution
        span = []
        while start_point <= end_point:
            span.append(start_point)
            start_point += self._resolution
        return span

    def _get_window(self, timestamp):
        for val in self._windows:
            if val > timestamp:
                return val

    def timestamp(self, date):
        for fmt in self.TIME_FORMATS:
            try:
                struct_time = time.strptime(date, fmt)
            except ValueError:
                continue
            return int(time.mktime(struct_time))
        raise ValueError(
            "time data '%s' does not match any acceptable format (%s)"
                % (date, ', '.join(["'%s'" % tf for tf in self.TIME_FORMATS])))

    def _uncumulate(self, entry):
        if not hasattr(self, '_previous'):
            self._previous = {}

        # This is first seen entry and it's not in previous. Create it
        if (entry['machine'], entry['container_name']) not in self._previous:
            # Save the cumulative data in prevous
            self._previous[entry['machine'], entry['container_name']] = {
                'cpu': entry.get('cpu_cumulative_usage'),
                'rxb': entry.get('rx_bytes'),
                'txb': entry.get('tx_bytes')}
            # nullify the current data because they're initial i.e. zeroes
            for i in 'cpu_cumulative_usage', 'rx_bytes', 'tx_bytes':
                if entry[i] is not None:
                    entry[i] = 0
            return entry

        for p in self._cumulatives.items():
            if all([ i is not None for i in entry.get(p[0]),
                    self._previous[ entry['machine'], entry['container_name'] ].get(p[1]) ]):
                diff = entry[ p[0] ] - self._previous[ entry['machine'], entry['container_name'] ][ p[1] ]
                self._previous[ entry['machine'], entry['container_name'] ][ p[1] ] = entry[ p[0] ]
                entry[ p[0] ] = diff
            elif entry[ p[0] ] is not None:
                self._previous[ entry['machine'], entry['container_name'] ][ p[1] ] = entry[ p[0] ]

    def _make_checker(self, containers):
        self._containers_checks = set()
        self._containers_map = {}
        for host in containers.keys():
            for item in containers[host]:
                self._containers_checks.add((host, item[1]))
                self._containers_map[item[1]] = item[2]

    @staticmethod
    def _get_item_id(entry):
        try:
            # we know that our string starts from 'k8n_'
            first_pos = entry['container_name'].index('_', 4)
            last_pos = entry['container_name'].index('_', first_pos+1)
            return entry['container_name'][first_pos+1:last_pos]
        except (ValueError, KeyError):
            return

    @staticmethod
    def _get_item_uuid(entry):
        try:
            last_pos = entry['container_name'].rindex('_')
            first_pos = entry['container_name'].rindex('_', 0, last_pos)
            return entry['container_name'][first_pos+1:last_pos]
        except (ValueError, KeyError):
            return

    def _is_wanted(self, entry):
        if entry['container_name'] == '/':
            self._wanted_map[entry['machine'], entry['container_name']] = '/'
            return True
        item = self._get_item_uuid(entry)
        if item is not None and (entry['machine'], item) in self._containers_checks:
            self._wanted_map[entry['machine'], entry['container_name']] = item
            return True
        item = self._get_item_id(entry)
        if item is not None and (entry['machine'], item) in self._containers_checks:
            self._wanted_map[entry['machine'], entry['container_name']] = item
            return True
        return False

    def _fold(self, entry):
        key = self._get_window(entry['time'])
        if key not in self._folded:
            self._folded[key] = {}

        if entry['machine'] not in self._folded[key]:
            self._folded[key][ entry['machine'] ] = {}

        try:
            unit = self._wanted_map[entry['machine'], entry['container_name']]
        except KeyError:
            return

        if unit not in self._folded[key][ entry['machine'] ]:
            self._folded[key][ entry['machine'] ][unit] = {}

        if entry['container_name'] not in self._folded[key][ entry['machine'] ][unit]:
            self._folded[key][entry['machine']][unit][entry['container_name']] = {
                'cpu': [], 'mem': [], 'rxb': [], 'txb': [],'fs': {}}

        root = self._folded[key][entry['machine']][unit][entry['container_name']]

        for p in dict(self._cumulatives.items()+[('memory_usage', 'mem')]).items():
            if entry[ p[0] ] is not None:
                #if p[0] == 'memory_usage':
                #    print entry[p[0]], entry['time'], key, entry['machine'], entry['container_name'], unit
                root[ p[1] ].append(entry[p[0]])

        if all([entry[i] is not None for i in 'fs_device', 'fs_usage', 'fs_limit']):
            if entry['fs_device'] not in root['fs']:
                root['fs'][ entry['fs_device'] ] = {'usage': [entry['fs_usage']], 'limit': entry['fs_limit']}
            else:
                root['fs'][ entry['fs_device'] ]['usage'].append(entry['fs_usage'])

    def _unfold(self):
        for cell in self._folded:
            for host in self._folded[cell]:
                for unit in self._folded[cell][host]:
                    for item in self._folded[cell][host][unit]:
                        root = self._folded[cell][host][unit][item]
                        r = {}
                        for i in self._cumulatives.values()+['mem']:
                            if root[i]:
                                r[i] = float(sum(root[i])) / len(root[i])

                        tick = {
                            'time_window': cell,
                            'host': host,
                            'unit_name': self._containers_map.get(unit, '/'),
                            'container': item,
                            'cpu': round(float(r['cpu']) / 600000000, 2),
                            'memory': round(r['mem'] / 1048576, 2),
                            'rxb': r['rxb'],
                            'txb': r['txb']}

                        if root.get('fs'):
                            tick['fs_data'] = ';'.join(
                                ':'.join(map(str,
                                             [i[0], sum(i[1]['usage'])/len(i[1]['usage']), i[1]['limit']]))
                                                for i in root['fs'].items())

                        self._unfolded.append(tick)

    def stats(self, containers):
        if not hasattr(self, '_containers_checks'):
            self._make_checker(containers)
        if not hasattr(self, '_data'):
            self._make_query()
        for points in reversed(self._data['points']):
            entry = dict(zip(self._data['columns'], points))
            if not self._is_wanted(entry):
                continue
            self._uncumulate(entry)
            self._fold(entry)
        self._unfold()
        return self._unfolded

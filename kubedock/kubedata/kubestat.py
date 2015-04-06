from influxdb import client
from .. import settings
from collections import OrderedDict
import time
from ..core import db
from ..pods import Pod
from ..users import User
from ..nodes.models import Node
import socket
import re
import requests
from influxdb.client import InfluxDBClientError

from ..utils import get_api_url


class KubeUnitResolver(object):
    def __init__(self):
        self._names = []
        self._containers = {}

    def by_unit(self, uuid):
        unit = db.session.query(Pod).get(uuid)
        if unit is None:
            return self._containers
        self._names.append(unit.name)
        self._get_containers()
        return self._containers



    def all(self):
        data = db.session.query(Pod).all()
        self._names.extend([i.name for i in data])
        self._get_containers()
        return self._containers

    def by_user(self, username=None):
        data = db.session.query(Pod).join(Pod.owner).filter_by(
            username=User.username).values(Pod.name)
        self._names.extend([i[0] for i in data])
        self._get_containers()
        return self._containers

    def __getattr__(self, name):
        if name == '_data':
            url = get_api_url('pods')
            r = requests.get(url)
            return r.json()
        raise AttributeError("No such attribute: %s" % (name,))

    def _get_containers(self):
        if 'items' not in self._data:
            return
        ip_patt = re.compile(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}')
        for item in self._data['items']:
            try:
                if item['labels']['name'] not in self._names:
                    continue
                host = item['currentState']['host']
                if ip_patt.match(host):
                    host = socket.gethostbyaddr(host)[0]
                if host not in self._containers:
                    self._containers[host] = []
                for c in item['desiredState']['manifest']['containers']:
                    self._containers[host].append((c['name'], item['id'], item['labels']['name']))
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
        'machine']

    TIME_FORMATS = [
        '%Y-%m-%d',
        '%Y-%m-%d %H:%M',
        '%Y-%m-%d %H:%M:%S']

    def __init__(self, start=None, end=None, resolution=60):

        self._folded = OrderedDict()
        self._unfolded = []
        self._wanted_map = {}
        self._resolution = resolution

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
        #except InfluxDBClientError:
        #    self.SELECT_COLUMNS = ['cpu_cumulative_usage', 'memory_usage', 'container_name', 'machine']
        #    colstr = ', '.join(['%s' % (c,) for c in self.SELECT_COLUMNS])
        #    conds = filter(None, [self._startcond, self._endcond])
        #    condstr = ' where %s' % (' and '.join(conds),) if len(conds) != 0 else ''
        #    self.query_str = 'select %s from %s%s;' % (colstr, settings.INFLUXDB_TABLE, condstr)
        #    self._make_query()


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
        if (entry['machine'], entry['container_name']) not in self._previous:
            self._previous[(entry['machine'], entry['container_name'])] = {
                'cpu': entry['cpu_cumulative_usage'],
                'rxb': entry['rx_bytes'] if ('rx_bytes' in entry and entry['rx_bytes'] is not None) else 0,
                'txb': entry['tx_bytes'] if ('tx_bytes' in entry and entry['tx_bytes'] is not None) else 0}
            if 'rx_bytes' in entry and 'tx_bytes' in entry:
                entry['rx_bytes'] = entry['tx_bytes'] = 0
            entry['cpu_cumulative_usage'] = 0
            return entry
        cpu_diff = entry['cpu_cumulative_usage'] - self._previous[(entry['machine'], entry['container_name'])]['cpu']

        curr_rxb = entry['rx_bytes'] if ('rx_bytes' in entry and entry['rx_bytes'] is not None) else 0
        curr_txb = entry['tx_bytes'] if ('tx_bytes' in entry and entry['tx_bytes'] is not None) else 0

        rxb_diff = curr_rxb - self._previous[(entry['machine'], entry['container_name'])]['rxb']
        txb_diff = curr_txb - self._previous[(entry['machine'], entry['container_name'])]['txb']

        self._previous[(entry['machine'], entry['container_name'])]['cpu'] = entry['cpu_cumulative_usage']
        self._previous[(entry['machine'], entry['container_name'])]['rxb'] = curr_rxb
        self._previous[(entry['machine'], entry['container_name'])]['txb'] = curr_txb
        entry['cpu_cumulative_usage'] = cpu_diff
        if 'rx_bytes' in entry and 'tx_bytes' in entry:
            entry['rx_bytes'] = rxb_diff
            entry['tx_bytes'] = txb_diff

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
            first_pos = entry['container_name'].index('_', 4) # we know that our string starts from 'k8n_'
            last_pos = entry['container_name'].index('.', first_pos)
            return entry['container_name'][first_pos+1:last_pos]
        except (ValueError, KeyError):
            return

    @staticmethod
    def _get_item_uuid(entry):
        try:
            last_pos = entry['container_name'].rindex('_') # we know that our string starts from 'k8n_'
            first_pos = entry['container_name'].rindex('_', 0, last_pos)
            return entry['container_name'][first_pos+1:last_pos]
        except (ValueError, KeyError):
            return

    def _is_wanted(self, entry):
        #if entry['container_name'] == '/system.slice':
        #    return True
        #last_pos = entry['container_name'].rfind('_')
        #if last_pos == -1:
        #    return False
        #first_pos = entry['container_name'].rfind('_', 0, last_pos)
        #if first_pos == -1:
        #    return False
        #item = entry['container_name'][first_pos+1:last_pos]

        # Pretty ugly workaround. First we search for UUID, then for uid
        item = self._get_item_uuid(entry)
        if item is not None and (entry['machine'], item) in self._containers_checks:
            self._wanted_map[entry['container_name']] = item
            return True
        item = self._get_item_id(entry)
        if item is not None and (entry['machine'], item) in self._containers_checks:
            self._wanted_map[entry['container_name']] = item
            return True
        return False

    #def _fold_system(self, key, entry):
    #    if 'system' not in self._folded[key][entry['machine']]:
    #        self._folded[key][entry['machine']]['system'] = {
    #            'cpu': 0, 'cpu_count': 0, 'mem': 0, 'mem_count': 0}
    #    self._folded[key][entry['machine']]['system']['cpu'] += entry['cpu_cumulative_usage']
    #    self._folded[key][entry['machine']]['system']['cpu_count'] += 1
    #    self._folded[key][entry['machine']]['system']['mem'] += entry['memory_usage']
    #    self._folded[key][entry['machine']]['system']['mem_count'] += 1

    def _fold_service(self, key, entry):
        #last_pos = entry['container_name'].rfind('_')
        #first_pos = entry['container_name'].rfind('_', 0, last_pos)
        #unit = entry['container_name'][first_pos+1:last_pos]
        try:
            unit = self._wanted_map[entry['container_name']]
        except KeyError:
            return
        if unit not in self._folded[key][entry['machine']]:
            self._folded[key][entry['machine']][unit] = {}
        if entry['container_name'] not in self._folded[key][entry['machine']][unit]:
            self._folded[key][entry['machine']][unit][entry['container_name']] = {
                'cpu': 0, 'cpu_count': 0, 'mem': 0, 'mem_count': 0,
                'rxb': 0, 'rxb_count': 0, 'txb': 0, 'txb_count': 0}
        self._folded[key][entry['machine']][unit][entry['container_name']]['cpu'] += entry['cpu_cumulative_usage']
        self._folded[key][entry['machine']][unit][entry['container_name']]['cpu_count'] += 1
        self._folded[key][entry['machine']][unit][entry['container_name']]['mem'] += entry['memory_usage']
        self._folded[key][entry['machine']][unit][entry['container_name']]['mem_count'] += 1
        self._folded[key][entry['machine']][unit][entry['container_name']]['rxb'] += entry['rx_bytes'] if 'rx_bytes' in entry else 0
        self._folded[key][entry['machine']][unit][entry['container_name']]['rxb_count'] += 1
        self._folded[key][entry['machine']][unit][entry['container_name']]['txb'] += entry['tx_bytes'] if 'tx_bytes' in entry else 0
        self._folded[key][entry['machine']][unit][entry['container_name']]['txb_count'] += 1

    def _fold(self, entry):
        key = self._get_window(entry['time'])
        if key not in self._folded:
            self._folded[key] = {}
        if entry['machine'] not in self._folded[key]:
            self._folded[key][entry['machine']] = {}
        #if entry['container_name'] == '/system.slice':
        #    self._fold_system(key, entry)
        #else:
        #    self._fold_service(key, entry)
        self._fold_service(key, entry)

    def _unfold(self):
        for cell in self._folded:
            for host in self._folded[cell]:
                #try:
                #    system = self._folded[cell][host].pop('system')
                #    sys_cpu = float(system['cpu']) / system['cpu_count']
                #    sys_mem = float(system['mem']) / system['mem_count']
                #except KeyError:
                #    continue
                for unit in self._folded[cell][host]:
                    for item in self._folded[cell][host][unit]:
                        cpu = mem = rxb = txb = 0
                        #if self._folded[cell][host][unit][item]['cpu_count'] != 0:
                        #    cpu = float(self._folded[cell][host][unit][item]['cpu']) / self._folded[cell][host][unit][item]['cpu_count']
                        if self._folded[cell][host][unit][item]['mem_count'] != 0:
                            mem = float(self._folded[cell][host][unit][item]['mem']) / self._folded[cell][host][unit][item]['mem_count']
                        if self._folded[cell][host][unit][item]['rxb_count'] != 0:
                            rxb = float(self._folded[cell][host][unit][item]['rxb']) / self._folded[cell][host][unit][item]['rxb_count']
                        if self._folded[cell][host][unit][item]['txb_count'] != 0:
                            txb = float(self._folded[cell][host][unit][item]['txb']) / self._folded[cell][host][unit][item]['txb_count']
                        #item_cpu = cpu / sys_cpu * 100 if sys_cpu != 0 else 0
                        #item_mem = mem / sys_mem * 100 if sys_mem != 0 else 0
                        self._unfolded.append({
                            'time_window': cell,
                            'host': host,
                            'unit_name': self._containers_map[unit],
                            'container': item,
                            #'cpu': item_cpu,
                            #'memory': item_mem,
                            'cpu': self._count_cpu(host, self._folded[cell][host][unit][item]['cpu']),
                            'memory': mem / 1048576,
                            'rxb': rxb,
                            'txb': txb})

    def _count_cpu(self, node, value):
        """
        Calculates percentage from nanoseconds of usage
        :param node: string -- node name or ipaddress
        :param value: float -- cpu usage value to calculate
        :return: float -- cpu usage percentage
        """
        try:
            cores = self._nodes[node]['cores']
            return float(value) / (1000000000 * self._resolution * cores)
        except KeyError:
            return 0


    def _get_nodes(self):
        self._nodes = {}
        data = db.session.query(Node.hostname, Node.cpu_cores, Node.ram).all()
        for node, cores, ram in data:
            self._nodes[node] = {'cores': cores, 'ram': ram}

    def stats(self, containers):
        if not hasattr(self, '_nodes'):
            self._get_nodes()
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
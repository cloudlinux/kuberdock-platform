import sys

import requests

from kubedock import settings
from kubedock.exceptions import InternalAPIError


class InfluxDBError(InternalAPIError):
    pass


class InfluxDBConnectionError(InfluxDBError):
    def __init__(self, e):
        message = 'Error during connection to influxdb cause of %s' % repr(e)
        super(InfluxDBConnectionError, self).__init__(message)


class InfluxDBUnexpectedAnswer(InfluxDBError):
    def __init__(self, e):
        message = 'Wrong answer from influxdb. Details: %s' % repr(e)
        super(InfluxDBUnexpectedAnswer, self).__init__(message)


def _query(query_str):
    url = 'http://{host}:{port}/query' \
        .format(host=settings.INFLUXDB_HOST,
                port=settings.INFLUXDB_PORT)
    params = {
        'q': query_str,
        'chunked': 'false',
        # 'epoch': 's',
        'db': settings.INFLUXDB_DATABASE,
        'u': settings.INFLUXDB_USER,
        'p': settings.INFLUXDB_PASSWORD
    }
    try:
        r = requests.get(
            url=url,
            params=params
        )
        return r.json()
    except requests.ConnectionError as e:
        raise InfluxDBConnectionError(e), None, sys.exc_info()[2]
    except ValueError as e:
        raise InfluxDBUnexpectedAnswer(e), None, sys.exc_info()[2]


def get_node_stat(nodename, start, end):
    b = QueryBuilder(start, end)
    f = node_filter(nodename)
    query_str = ' '.join((
        b.start_new().with_selector(CpuLimitSelector).with_filter(f).build(),
        b.start_new().with_selector(CpuUsageSelector).with_filter(f).build(),
        b.start_new().with_selector(MemoryLimitSelector).with_filter(
            f).build(),
        b.start_new().with_selector(MemoryUsageSelector).with_filter(
            f).build(),
        b.start_new().with_selector(RxbSelector).with_filter(f).build(),
        b.start_new().with_selector(TxbSelector).with_filter(f).build(),
        b.start_new().with_selector(FsLimitSelector).with_filter(f).build(),
        b.start_new().with_selector(FsUsageSelector).with_filter(f).build(),
    ))
    response = _query(query_str)
    data = response['results']
    return {
        'cpu/request': transform_flat_data(data[0]),
        'cpu/usage_rate': transform_flat_data(data[1]),
        'memory/request': transform_flat_data(data[2]),
        'memory/usage': transform_flat_data(data[3]),
        'network/rx_rate': transform_flat_data(data[4]),
        'network/tx_rate': transform_flat_data(data[5]),
        'filesystem/limit': transform_fs_grouped_data(data[6]),
        'filesystem/usage': transform_fs_grouped_data(data[7]),
    }


def get_pod_stat(pod_name, start, end):
    b = QueryBuilder(start, end)
    f = pod_filter(pod_name)
    query_str = ' '.join((
        b.start_new().with_selector(CpuLimitSelector).with_filter(f).build(),
        b.start_new().with_selector(CpuUsageSelector).with_filter(f).build(),
        b.start_new().with_selector(MemoryLimitSelector).with_filter(
            f).build(),
        b.start_new().with_selector(MemoryUsageSelector).with_filter(
            f).build(),
        b.start_new().with_selector(RxbSelector).with_filter(f).build(),
        b.start_new().with_selector(TxbSelector).with_filter(f).build(),
    ))
    response = _query(query_str)
    data = response['results']
    return {
        'cpu/request': transform_flat_data(data[0]),
        'cpu/usage_rate': transform_flat_data(data[1]),
        'memory/request': transform_flat_data(data[2]),
        'memory/usage': transform_flat_data(data[3]),
        'network/rx_rate': transform_flat_data(data[4]),
        'network/tx_rate': transform_flat_data(data[5]),
    }


def get_container_stat(pod_name, container_name, start, end):
    b = QueryBuilder(start, end)
    f = container_filter(pod_name, container_name)
    query_str = ' '.join((
        b.start_new().with_selector(CpuLimitSelector).with_filter(f).build(),
        b.start_new().with_selector(CpuUsageSelector).with_filter(f).build(),
        b.start_new().with_selector(MemoryLimitSelector).with_filter(
            f).build(),
        b.start_new().with_selector(MemoryUsageSelector).with_filter(
            f).build(),
    ))
    response = _query(query_str)
    data = response['results']
    return {
        'cpu/request': transform_flat_data(data[0]),
        'cpu/usage_rate': transform_flat_data(data[1]),
        'memory/request': transform_flat_data(data[2]),
        'memory/usage': transform_flat_data(data[3]),
    }


class QueryBuilder(object):
    template = 'select {fields} from "{measurement}" ' \
               'where {filter} ' \
               "and time >= '{start}' and time <= '{end}' " \
               '{group_by_section}' \
               'order by time asc;'

    def __init__(self, start, end):
        self._start = start
        self._end = end
        self._source = {}

    def start_new(self):
        self._source = {}
        return self

    def build(self):
        source = self._source
        selector = source['selector']
        if selector.group_by:
            group_by = 'group by "%s" ' % selector.group_by
        else:
            group_by = ""
        return self.template.format(
            fields=', '.join(selector.fields),
            measurement=selector.measurement,
            filter=source['filter'],
            group_by_section=group_by,
            start=self._start,
            end=self._end
        )

    def with_selector(self, selector):
        self._source['selector'] = selector
        return self

    def with_filter(self, filter_):
        self._source['filter'] = filter_
        return self


def node_filter(nodename):
    return "nodename = '%s' and type = 'node'" % nodename


def pod_filter(pod_name):
    return "namespace_name = '%s' and type = 'pod'" % pod_name


def container_filter(pod_name, container_name):
    return "namespace_name = '%s' and container_name = '%s' " \
           "and type = 'pod_container'" \
           % (pod_name, container_name)


class SelectorBase(object):
    fields = ('value',)
    measurement = 'some_measurement'
    group_by = None


class CpuLimitSelector(SelectorBase):
    measurement = 'cpu/request'


class CpuUsageSelector(SelectorBase):
    measurement = 'cpu/usage_rate'


class MemoryLimitSelector(SelectorBase):
    measurement = 'memory/request'


class MemoryUsageSelector(SelectorBase):
    measurement = 'memory/usage'


class RxbSelector(SelectorBase):
    measurement = 'network/rx_rate'


class TxbSelector(SelectorBase):
    measurement = 'network/tx_rate'


class FsLimitSelector(SelectorBase):
    measurement = 'filesystem/limit'
    group_by = 'resource_id'


class FsUsageSelector(SelectorBase):
    measurement = 'filesystem/usage'
    group_by = 'resource_id'


def transform_flat_data(data):
    try:
        d = data['series'][0]
    except KeyError:
        return []
    values = [Point(*value) for value in d['values']]
    return values


def transform_fs_grouped_data(data):
    try:
        d = data['series']
    except KeyError:
        return []
    values = [
        {
            'resource_id': s['tags']['resource_id'],
            'values': [Point(*x) for x in s['values']]
        }
        for s in d
        ]
    return values


class Point(object):
    def __init__(self, time, value):
        self.time = time
        self.value = value

    def __repr__(self):
        return 'Point(%s: %s)' % (self.time, self.value)

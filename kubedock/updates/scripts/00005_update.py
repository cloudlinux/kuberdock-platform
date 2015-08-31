import json
from kubedock.api import create_app
from kubedock.kapi.helpers import KubeQuery


paths = ['metadata.labels',
         'spec.selector',
         'spec.template.metadata.labels',
         'spec.template.spec.selector']


def _add_label(replace_map, items, using_label='name', add_label='kuberdock-pod-uid'):
    for item in items:
        for path in paths:
            obj = reduce(lambda obj, key: obj.get(key, {}), path.split('.'), item)
            try:
                namespace = item['metadata']['namespace']
                obj[add_label] = replace_map[obj[using_label], namespace]
            except KeyError:
                pass


def _del_label(replace_map, items, del_label='name', if_label='kuberdock-pod-uid'):
    for item in items:
        for path in paths:
            obj = reduce(lambda obj, key: obj.get(key, {}), path.split('.'), item)
            try:
                namespace = item['metadata']['namespace']
                if replace_map[obj[del_label], namespace] == obj[if_label]:
                    del obj[del_label]
            except KeyError:
                pass


def _put(kind, *items):
    """Send items of given kind to kubernetes"""
    api = KubeQuery()
    for item in items:
        try:
            response = api._put([kind, item['metadata']['name']],
                                json.dumps(item), ns=item['metadata']['namespace'])
            if response['kind'].lower() == 'status':
                print('Warning: {kind} {response}'.format(kind, response))
        except KeyError:
            pass


def _replace_labels(replace_map, old_label, new_label):
    api = KubeQuery()

    for kind in ('pods', 'replicationcontrollers', 'services'):
        items = api._get([kind])['items']
        _add_label(replace_map, items, using_label=old_label, add_label=new_label)
        _put(kind, *items)

    for kind in ('services', 'replicationcontrollers', 'pods'):
        items = api._get([kind])['items']
        _del_label(replace_map, items, del_label=old_label, if_label=new_label)
        _put(kind, *items)


def upgrade(upd, with_testing, *args, **kwargs):
    print 'upgrade routine has been called'
    app = create_app()
    with app.app_context():
        from kubedock.pods.models import Pod

        name_to_id_map = {(pod.name, pod.namespace): pod.id
                          for pod in Pod.query.all()}
        _replace_labels(name_to_id_map, 'name', 'kuberdock-pod-uid')


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    print 'downgrade routine has been called'
    app = create_app()
    with app.app_context():
        from kubedock.pods.models import Pod

        id_to_name_map = {(pod.id, pod.namespace): pod.name
                          for pod in Pod.query.all()}
        _replace_labels(id_to_name_map, 'kuberdock-pod-uid', 'name')

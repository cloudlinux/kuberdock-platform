import os

import yaml

from kubedock.core import ssh_connect
from kubedock.kapi.helpers import replace_pod_config
from kubedock.kapi.podcollection import PodCollection, PodNotFound
from kubedock.pods import Pod
from kubedock.predefined_apps.models import PredefinedApp
from kubedock.updates import helpers

DOCKER_VERSION = '1.12.1-2.el7'
DOCKER = 'docker-{ver}'.format(ver=DOCKER_VERSION)
SELINUX = 'docker-selinux-{ver}'.format(ver=DOCKER_VERSION)


def _upgrade_docker(with_testing):
    helpers.remote_install(SELINUX, with_testing)
    helpers.remote_install(DOCKER, with_testing)
    res = helpers.restart_service('docker')
    if res != 0:
        raise helpers.UpgradeError('Failed to restart docker. {}'.format(res))


def upgrade(upd, with_testing, *args, **kwargs):
    pas_to_upgrade = {
        pa.id: pa for pa in PredefinedApp.query.all()
        if _pa_contains_originroot_hack(pa)}

    if not pas_to_upgrade:
        upd.print_log('No outdated PAs. Skipping')
        return

    pods_to_upgrade = Pod.query.filter(
        Pod.template_id.in_(pas_to_upgrade.keys())).all()

    _remove_lifecycle_section_from_pods(upd, pods_to_upgrade, pas_to_upgrade)
    _update_predefined_apps(upd, pas_to_upgrade)
    _mark_volumes_as_prefilled(pas_to_upgrade, pods_to_upgrade)


def downgrade(upd, with_testing, exception, *args, **kwargs):
    pass


def upgrade_node(upd, with_testing, env, *args, **kwargs):
    _upgrade_docker(with_testing)


def downgrade_node(upd, with_testing, env, exception, *args, **kwargs):
    pass


def contains_origin_root(container):
    try:
        return '/originroot/' in str(
            container['lifecycle']['postStart']['exec']['command'])
    except KeyError:
        return False


def _pa_contains_originroot_hack(app):
    tpl = yaml.load(app.template)
    try:
        containers = tpl['spec']['template']['spec']['containers']
    except KeyError:
        return False

    return any(contains_origin_root(c) for c in containers)


def _remove_lifecycle_section_from_pods(upd, pods, pas):
    # PodCollection.update({'command': 'change_config'}) can't delete keys
    # thus mocking instead
    def _mock_lifecycle(config):
        for container in config['containers']:
            if not contains_origin_root(container):
                continue
            container['lifecycle'] = {
                'postStart': {'exec': {'command': ['/bin/true']}}
            }
        return config

    def _set_prefill_flag(config, pod):
        prefilled_volumes = _extract_prefilled_volumes_from_pod(pas, pod)

        for container in config['containers']:
            for vm in container.get('volumeMounts', []):
                if vm['name'] in prefilled_volumes:
                    vm['kdCopyFromImage'] = True

    collection = PodCollection()

    for pod in pods:
        config = _mock_lifecycle(pod.get_dbconfig())
        _set_prefill_flag(config, pod)
        config['command'] = 'change_config'

        try:
            replace_pod_config(pod, config)
            collection.update(pod.id, config)
            upd.print_log('POD {} config patched'.format(pod.id))
        except PodNotFound:
            upd.print_log('Skipping POD {}. Not found in K8S'.format(pod.id))


def _mark_volumes_as_prefilled(pas, pods):
    for pod in pods:
        prefilled_volumes = _extract_prefilled_volumes_from_pod(pas, pod)
        config = pod.get_dbconfig()

        paths_to_volumes = [
            v['hostPath']['path'] for v in config['volumes']
            if v['name'] in prefilled_volumes]

        ssh, err = ssh_connect(pod.pinned_node)

        if err:
            raise Exception(err)

        for path in paths_to_volumes:
            lock_path = os.path.join(path, '.kd_prefill_succeded')
            ssh.exec_command('touch {}'.format(lock_path))


def _extract_prefilled_volumes_from_pod(pas, pod):
    template = yaml.load(pas[pod.template_id].template)
    containers = (c for c in
                  template['spec']['template']['spec']['containers'])
    return {vm['name'] for c in containers for vm in c['volumeMounts']}


def _update_predefined_apps(upd, kd_pas):
    for pa in kd_pas.values():
        template = yaml.load(pa.template)

        try:
            containers = template['spec']['template']['spec']['containers']
        except KeyError:
            upd.print_log('Unexpected PA {} found. Skipping'.format(pa.id))
            continue

        for container in containers:
            container.pop('lifecycle', None)
            for mount in container.get('volumeMounts', []):
                mount['kdCopyFromImage'] = True

        pa.template = yaml.dump(template, default_flow_style=False)
        pa.save()
        upd.print_log('PA {} patched'.format(pa.name))

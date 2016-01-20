from copy import deepcopy
from kubedock.pods.models import PersistentDisk, Pod, db


def with_size(volumes, owner_id):
    volumes = deepcopy(volumes)
    for volume in volumes:
        pd = volume.get('persistentDisk')
        if pd and not pd.get('pdSize'):
            pd_in_db = PersistentDisk.query.filter_by(name=pd.get('pdName'),
                                                      owner_id=owner_id).first()
            pd['pdSize'] = pd_in_db.size if pd_in_db is not None else 1
    return volumes


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Add default Persistent Disks size in pods config...')

    pods = Pod.query.all()
    for pod in pods:
        upd.print_log('Processing pod {0}'.format(pod.name))
        config = pod.get_dbconfig()
        config['volumes_public'] = with_size(config.get('volumes_original', []), pod.owner_id)
        pod.set_dbconfig(config, save=False)
    for pod in pods:
        config = pod.get_dbconfig()
        config.pop('volumes_original', None)
        pod.set_dbconfig(config, save=False)
    db.session.commit()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Set volumes_original back...')

    for pod in Pod.query.all():
        upd.print_log('Processing pod {0}'.format(pod.name))
        config = pod.get_dbconfig()
        if 'volumes_original' not in config:
            config['volumes_original'] = config.get('volumes_public', [])
        pod.set_dbconfig(config, save=False)
    db.session.commit()

from kubedock.pods.models import PersistentDisk, Pod


def get_persistent_disk(upd, internal_volume):
    if 'rbd' in internal_volume:
        drive_name = internal_volume['rbd']['image']
        size = internal_volume['rbd'].get('size', 1)
    elif 'awsElasticBlockStore' in internal_volume:
        drive_name = internal_volume['awsElasticBlockStore']['drive']
        size = internal_volume['awsElasticBlockStore'].get('size', 1)
    else:
        raise ValueError('Incorrect volume! {0}'.format(internal_volume))
    pd = PersistentDisk.query.filter_by(drive_name=drive_name).first()
    if pd is None:
        upd.print_log('PD was not found {0}'.format(internal_volume))
        pd = PersistentDisk(drive_name=drive_name, size=size).save()
    return pd


def internal_to_original(upd, internal_volumes):
    volumes = []
    for internal_volume in internal_volumes:
        upd.print_log('Processing volume {0}'.format(internal_volume))
        volume = {'name': internal_volume['name']}
        if 'hostPath' in internal_volume:
            volume['localStorage'] = True
        else:
            pd = get_persistent_disk(upd, internal_volume)
            volume['persistentDisk'] = {'pdName': pd.name, 'pdSize': pd.size}
        volumes.append(volume)
    return volumes


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Create Persistent Disks in database and '
                  'restore original volumes config...')

    for pod in Pod.query.all():
        upd.print_log('Processing pod {0}'.format(pod.name))
        config = pod.get_dbconfig()
        config['volumes_original'] = internal_to_original(upd, config.get('volumes', []))
        pod.set_dbconfig(config)


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')

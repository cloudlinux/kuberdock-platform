from kubedock.usage.models import db, ContainerState


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Filling "kubes" field in old container states...')

    for cs in ContainerState.query.all():
        containers = cs.pod.get_dbconfig('containers')
        try:
            cs.kubes = (container.get('kubes', 1) for container in containers
                        if container['name'] == cs.container_name).next()
        except StopIteration:
            upd.print_log('Container not found: {0}'.format(cs.container_name))
    db.session.commit()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('No downgrade needed')

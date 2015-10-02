from kubedock.core import db


PREFIX = 'docker://'


def upgrade(upd, with_testing, *args, **kwargs):
    from kubedock.usage.models import ContainerState
    upd.print_log('Cut off "{0}" from ContainerState.docker_id'.format(PREFIX))

    for cs in ContainerState.query.all():

        if cs.docker_id.startswith(PREFIX):
            docker_id = cs.docker_id.split(PREFIX)[-1]

            ContainerState.query.filter_by(
                pod_id=cs.pod_id,
                container_name=cs.container_name,
                docker_id=docker_id,
                kubes=cs.kubes,
                start_time=cs.start_time,
            ).delete()

            cs.docker_id = docker_id

    db.session.commit()


def downgrade(upd, with_testing, exception, *args, **kwargs):
    from kubedock.usage.models import ContainerState
    upd.print_log('Add "{0}" to ContainerState.docker_id'.format(PREFIX))

    for cs in ContainerState.query.all():

        if not cs.docker_id.startswith(PREFIX):
            docker_id = PREFIX + cs.docker_id

            ContainerState.query.filter_by(
                pod_id=cs.pod_id,
                container_name=cs.container_name,
                docker_id=docker_id,
                kubes=cs.kubes,
                start_time=cs.start_time,
            ).delete()

            cs.docker_id = docker_id

    db.session.commit()

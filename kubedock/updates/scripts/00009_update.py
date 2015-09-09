from kubedock.pods.models import DockerfileCache


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Clearing dockerfiles cache...')
    DockerfileCache.query.delete()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    pass
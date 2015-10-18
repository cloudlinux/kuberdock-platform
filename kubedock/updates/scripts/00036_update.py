from kubedock.pods.models import db, DockerfileCache, ImageCache


def upgrade(upd, with_testing, *args, **kwargs):
    upd.print_log('Clearing cache...')
    db.session.query(DockerfileCache).delete()
    db.session.query(ImageCache).delete()
    db.session.commit()


def downgrade(upd, with_testing,  exception, *args, **kwargs):
    upd.print_log('Sorry, no downgrade provided')

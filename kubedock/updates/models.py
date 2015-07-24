from ..core import db
from kubedock.models_mixin import BaseModelMixin


class Updates(BaseModelMixin, db.Model):
    __tablename__ = 'updates'
    fname = db.Column(db.Text, primary_key=True, nullable=False)
    status = db.Column(db.Text, nullable=False)
    log = db.Column(db.Text, nullable=True)
    last_step = db.Column(db.Integer, default=0, nullable=True)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True)

    @property
    def checkpoint(self):
        return self.last_step or 0

    @checkpoint.setter
    def checkpoint(self, val):
        self.last_step = val
        self.save()

    def print_log(self, *msg):
        if len(msg) > 0:
            m = map(str, msg)
            print ' '.join(m)
            self.log = ' '.join([(self.log or '')] + m + ['\n'])
            self.save()

    def __repr__(self):
        return "<Update(fname='{0}', status='{1}')>".format(self.fname,
                                                            self.status)

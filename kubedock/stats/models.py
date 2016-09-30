from ..core import db


class StatWrap5Min(db.Model):
    __tablename__ = 'stat_wrap_5min'
    __table_args__ = (
        db.PrimaryKeyConstraint(
            'time_window',
            'host',
            'unit_name',
            'container',
            name='window_entry'),
    )
    time_window = db.Column(db.Integer, nullable=False)
    host = db.Column(db.String(64), nullable=False)
    unit_name = db.Column(db.String(255), nullable=False, index=True)
    container = db.Column(db.String(255), nullable=False, index=True)
    cpu = db.Column(db.Float, nullable=False, default=0.0)
    memory = db.Column(db.Float, nullable=False, default=0.0)
    rxb = db.Column(db.Float, nullable=False, default=0.0)
    txb = db.Column(db.Float, nullable=False, default=0.0)
    fs_data = db.Column(db.Text, nullable=True)

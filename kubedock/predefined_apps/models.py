from flask import current_app
from ..core import db
from ..models_mixin import BaseModelMixin


class PredefinedApp(db.Model, BaseModelMixin):
    __tablename__ = 'predefined_apps'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True, nullable=False)
    template = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    def __repr__(self):
        return "<PredefinedApp(id='{0}', user_id='{1}')>".format(self.id, self.user_id)

    def to_dict(self):
        return {'id': self.id, 'template': self.template, 'user_id': self.user_id}

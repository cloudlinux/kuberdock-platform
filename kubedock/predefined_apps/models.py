from datetime import datetime
from hashlib import sha1

from kubedock.exceptions import PredefinedAppExc
from ..core import db
from ..models_mixin import BaseModelMixin


class PredefinedApp(BaseModelMixin, db.Model):
    __tablename__ = 'predefined_apps'

    CREATE_FIELDS = ['name', 'origin', 'search_available', 'icon']

    id = db.Column(db.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    name = db.Column(db.String(255), default='', nullable=False)
    qualifier = db.Column(db.String(40), default='', nullable=False,
                          index=True)
    origin = db.Column(db.String(255), default='unknown', nullable=False)
    templates = db.relationship("PredefinedAppTemplate",
                                backref="predefined_app", lazy='dynamic')
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    modified = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    icon = db.Column(db.Text, nullable=True)
    search_available = db.Column(db.Boolean, default=True)

    _new_version = None
    template_model = None

    def __init__(self, *args, **kwargs):
        template = kwargs.pop('template', None)
        values = {k: v for k, v in kwargs.iteritems() if k in
                  self.CREATE_FIELDS}
        super(PredefinedApp, self).__init__(*args, **values)
        sha = sha1()
        sha.update(str(datetime.now()))
        self.qualifier = sha.hexdigest()
        if template:
            self.template = template

    def __repr__(self):
        return "<PredefinedApp(id={0}, name='{1}', qualifier='{2}')>".format(
            self.id, self.name, self.qualifier)

    def select_version(self, version_id, new_version=None):
        """
        Select version for edit
        :param new_version: flag to create new version
        :param version: int -> version of PA
        """
        self.template_model = self.templates.filter_by(id=version_id).first()
        if not self.template_model and not new_version:
            raise PredefinedAppExc.NoSuchPredefinedAppVersion()
        self._new_version = new_version

    def set_active_version(self, version_id):
        version = self.templates.filter_by(is_deleted=False,
                                           id=version_id).first()
        if version:
            self.templates.update({'active': False},
                                  synchronize_session='fetch')
            version.active = True
            db.session.flush()
        else:
            raise PredefinedAppExc.NoSuchPredefinedAppVersion

    def save(self, deferred_commit=False):
        self.modified = datetime.utcnow()
        super(PredefinedApp, self).save(deferred_commit)

    def get_template_object(self):
        if self.template_model:
            return self.template_model
        if self._new_version or not self.id:
            return None
        return self.templates.filter_by(active=True).first()

    @property
    def active(self):
        app_template = self.get_template_object()
        if app_template:
            return app_template.active

    @active.setter
    def active(self, value):
        app_template = self.get_template_object()
        if app_template:
            if value:
                self.set_active_version(app_template.id)
            elif app_template.active:
                raise PredefinedAppExc.ActiveVersionNotRemovable()
            db.session.flush()
        else:
            raise PredefinedAppExc.NoSuchPredefinedAppVersion

    @property
    def switchingPackagesAllowed(self):
        app_template = self.get_template_object()
        if app_template:
            return app_template.switching_allowed

    @switchingPackagesAllowed.setter
    def switchingPackagesAllowed(self, value):
        app_template = self.get_template_object()
        if not app_template:
            self.create_new_template(switching_allowed=value)
        else:
            app_template.switching_allowed = value

    @property
    def template(self):
        tpl = self.get_template_object()
        return tpl.template if tpl else ''

    @template.setter
    def template(self, value):
        app_template = self.get_template_object()
        if not app_template:
            app_template = self.create_new_template(template=value)
        else:
            app_template.template = value
            app_template.modified = datetime.utcnow()
            self.modified = datetime.utcnow()
        db.session.flush()

    def create_new_template(self, template='', **kwargs):
        if not self.id:
            db.session.add(self)
            db.session.flush()
        app_template = PredefinedAppTemplate(predefined_app_id=self.id,
                                             modified=datetime.utcnow(),
                                             template=template,
                                             **kwargs)
        self.template_model = app_template
        db.session.add(app_template)
        db.session.flush()
        if len(self.templates.all()) == 1:
            app_template.active = True
        return app_template

    def to_dict(self, include=None, exclude=()):
        versions = [version for version in self.templates.filter_by(
                    is_deleted=False)]
        data = {
            'id': self.id,
            'name': self.name,
            'icon': self.icon,
            'qualifier': self.qualifier,
            'origin': self.origin,
            'template': self.template,
            'created': self.created,
            'modified': self.modified,
            'activeVersionID': next(v.id for v in versions if v.active),
            'templates': [v.to_dict() for v in versions],
            'search_available': self.search_available,
        }
        return {key: val for key, val in data.items() if key not in exclude}


class PredefinedAppTemplate(BaseModelMixin, db.Model):
    __tablename__ = 'predefined_app_templates'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True,
                   nullable=False)
    predefined_app_id = db.Column(db.Integer,
                                  db.ForeignKey("predefined_apps.id"),
                                  nullable=False)
    template = db.Column(db.Text, nullable=False)
    active = db.Column(db.Boolean, default=False, nullable=False)
    switching_allowed = db.Column(db.Boolean, default=True, nullable=False)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    created = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)
    modified = db.Column(db.DateTime, nullable=True, default=datetime.utcnow)

    __table_args__ = (
        db.Index('predefined_app_id_active', 'predefined_app_id', 'active',
                 unique=True, postgresql_where=active),
        db.CheckConstraint('NOT (active AND is_deleted)'),
    )

    def to_dict(self, include=None, exclude=None):
        result = super(PredefinedAppTemplate, self) \
            .to_dict(include,
                     [
                         'predefined_app_id',
                         'is_deleted',
                         'switching_allowed'])
        result['switchingPackagesAllowed'] = self.switching_allowed
        return result

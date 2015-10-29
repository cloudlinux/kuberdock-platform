import datetime

from ..core import db

class SystemSettings(db.Model):
    """Simple settings in form key-value for syste-wide settings store.
    These settings not attached to any particular user.
    Name of the setting is unique and presents exactly one setting.
    Settings actually will not be deleted, instead of this there is 'deleted'
    field which marks a setting as deleted, so we can access history of setting
    changes.
    All settings names will be converted to lowercase in save and search
    methods.
    """
    __tablename__ = 'system_settings'

    id = db.Column(db.Integer, primary_key=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    value = db.Column(db.Text)
    created = db.Column(db.DateTime, nullable=False)
    deleted = db.Column(db.DateTime, nullable=True)

    @classmethod
    def save_setting(cls, name, value):
        if name:
            name = name.lower()
        entity = cls.get_by_name(name)
        if entity:
            if entity.value == value:
                return entity
            entity.deleted = datetime.datetime.utcnow()
        entity = cls(name=name, value=value, created=datetime.datetime.utcnow())
        db.session.add(entity)
        db.session.commit()
        return entity

    @classmethod
    def read_setting(cls, name, default_value=None):
        entity = cls.get_by_name(name)
        if entity:
            return entity.value
        if default_value is not None:
            return default_value
        return None

    @classmethod
    def get_by_name(cls, name):
        if name:
            name = name.lower()
        return cls.query.filter(cls.name == name, cls.deleted == None).first()

    @classmethod
    def delete_setting(cls, name):
        entity = cls.get_by_name(name)
        if entity:
            entity.deleted = datetime.datetime.utcnow()
            db.session.commit()

    @classmethod
    def get_all(cls, as_dict=False):
        items = cls.query.filter(cls.deleted == None).all()
        if not as_dict:
            return items
        return {item.name: item.value for item in items}

# Index to search settings by name and selection of all actual settings
db.Index('ix_deleted_name', SystemSettings.deleted, SystemSettings.name)

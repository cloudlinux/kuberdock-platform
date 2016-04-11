from collections import OrderedDict
from sqlalchemy.ext.orderinglist import ordering_list

from ..core import db
from ..rbac import get_user_role
from ..rbac.models import Role
from ..models_mixin import BaseModelMixin


class Menu(BaseModelMixin, db.Model):
    __tablename__ = 'menus'

    REGION_NAVBAR, REGION_FOOTER = 1, 2
    REGIONS = (
        (REGION_NAVBAR, 'navbar'),
        (REGION_FOOTER, 'footer'),
    )

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    region = db.Column(db.Integer, default=REGION_NAVBAR, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    items = db.relationship('MenuItem', backref=db.backref("menu"))
    is_active = db.Column(db.Boolean, default=True)


class MenuItemRole(BaseModelMixin, db.Model):
    __tablename__ = 'menuitem_roles'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    menuitem_id = db.Column(db.Integer, db.ForeignKey('menus_items.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('rbac_role.id'))
    role = db.relationship('Role', backref=db.backref('menus_assocs'))
    menuitem = db.relationship('MenuItem', backref=db.backref('roles_assocs'))


class MenuItem(BaseModelMixin, db.Model):
    __tablename__ = 'menus_items'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('menus_items.id'))
    children = db.relationship(
        'MenuItem', cascade="all",
        collection_class=ordering_list('ordering'),
        backref=db.backref("parent", remote_side='MenuItem.id'),
        order_by="MenuItem.ordering",)
    path = db.Column(db.String(1000), nullable=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'))
    name = db.Column(db.String(255), nullable=False)
    ordering = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return "MenuItem(name=%r, id=%r, parent_id=%r)" % (
            self.name, self.id, self.parent_id)

    @classmethod
    def get_menu(cls):
        role_name = get_user_role()
        items = cls.query.join(Menu).filter(
            Menu.region == Menu.REGION_NAVBAR,
            cls.parent_id.is_(None),
            cls.is_active).order_by(cls.ordering).all()
        menu = OrderedDict()
        role = Role.filter(Role.rolename == role_name).first()
        for item in items:
            if MenuItemRole.filter(MenuItemRole.role == role,
                                   MenuItemRole.menuitem == item).all():
                menu[item.name] = {}
                if item.path:
                    menu[item.name]['path'] = item.path
        children = cls.query.join(Menu).filter(
            Menu.region == Menu.REGION_NAVBAR,
            cls.parent_id.isnot(None),
            cls.is_active).order_by(cls.ordering).all()
        for child in children:
            parent_name = child.parent.name
            if parent_name in menu:
                items = menu[parent_name].setdefault('children', [])
                items.append({'name': child.name, 'path': child.path})
        rv = []
        for name, data in menu.items():
            data['name'] = name
            rv.append(data)
        return rv

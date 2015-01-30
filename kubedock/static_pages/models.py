from datetime import datetime
from flask import render_template_string
from sqlalchemy.orm.collections import attribute_mapped_collection

from ..core import db
from ..models_mixin import BaseModelMixin
from .utils import slugify


class Menu(BaseModelMixin, db.Model):
    __tablename__ = 'menus'

    REGION_NAVBAR, REGION_FOOTER = 1, 2
    REGIONS = (
        (REGION_NAVBAR, 'navbar'),
        (REGION_FOOTER, 'footer'),
    )

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    region = db.Column(db.Integer, default=REGION_NAVBAR, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    items = db.relationship('MenuItem', backref=db.backref("menu"))
    is_active = db.Column(db.Boolean, default=True)

    def __unicode__(self):
        return self.name

    @classmethod
    def get_active(cls):
        menu_list = cls.filter_by(is_active=True)
        menus = dict([(m.region_repr, m) for m in menu_list])
        return menus

    def get_items(self):
        items = MenuItem.filter_by(menu_id=self.id, parent_id=None).all()
        return items

    @classmethod
    def get_dynatree_list(cls):
        menu_list = cls.filter_by(is_active=True)
        menus = dict([(m.region_repr, m.to_dynatree()) for m in menu_list])
        return menus

    def render(self):
        if self.region == Menu.REGION_NAVBAR:
            return render_template_string("""
                <div class="collapse navbar-collapse">
                    <ul class="nav navbar-nav">
                        {% for item in items %}<li>
                            {{ item.render()|safe }}
                        </li>
                        {% endfor %}
                    </ul>
                </div><!--/.nav-collapse -->
            """, items=self.get_items())

    @property
    def region_repr(self):
        return dict(self.REGIONS)[self.region]

    def to_dict(self, include=None, exclude=None):
        return dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            region=self.region,
            name=self.name,
            items=[item.to_dict(include=include, exclude=exclude)
                   for item in self.items.values()]
        )

    def to_dynatree(self):
        return dict(
            key=self.id,
            title=self.name,
            children=[item.to_dynatree() for item in self.get_items()],
            unselectable=True,
            # href='menu/%s/' % self.id,
            data=dict(
                id=self.id,
                ts=self.ts.isoformat(sep=' ')[:19],
                name=self.name,
                created_by_id=self.created_by_id,
                region=self.region,
                t='menu',
                is_active=self.is_active
            )
        )

    def form_render(self):
        context = dict(
            regions=[dict(id=r[0], name=r[1]) for r in Menu.REGIONS],
            menu=self
        )
        return render_template_string('menus/inc/menu_form.html', **context)


class MenuItem(BaseModelMixin, db.Model):
    __tablename__ = 'menus_items'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('menus_items.id'))
    children = db.relationship(
        'MenuItem', cascade="all",
        collection_class=attribute_mapped_collection('name'),
        backref=db.backref("parent", remote_side='MenuItem.id'))
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    path = db.Column(db.String(1000), nullable=True)
    menu_id = db.Column(db.Integer, db.ForeignKey('menus.id'))
    name = db.Column(db.String(255), nullable=False)
    page_id = db.Column(db.Integer, db.ForeignKey('pages.id'))
    ordering = db.Column(db.Integer, default=0)
    is_group_label = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # def __init__(self, name, parent=None):
    #     self.name = name
    #     self.parent = parent

    def __repr__(self):
        return "MenuItem(name=%r, id=%r, parent_id=%r)" % (
            self.name, self.id, self.parent_id)

    def to_dict(self, include=None, exclude=None):
        page = self.page
        return dict(
            id=self.id,
            parent_id=self.parent_id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            path=self.path,
            menu_id=self.menu_id,
            name=self.name,
            page=page.id if page else None,
            ordering=self.ordering,
            is_group_label=self.is_group_label,
            is_active=self.is_active,
            children=[(item.id, item.to_dict(include=include, exclude=None))
                      for item in self.children.values()]
        )

    def to_dynatree(self):
        page = self.page
        return dict(
            key=self.id,
            # href='item/%s/' % self.id,
            title=self.name,
            children=[item.to_dynatree() for item in self.children.values()],
            data=dict(
                id=self.id,
                name=self.name,
                parent_id=self.parent_id,
                ts=self.ts.isoformat(sep=' ')[:19],
                created_by_id=self.created_by_id,
                path=self.path,
                menu_id=self.menu_id,
                region=self.menu.region,
                region_repr=self.menu.region_repr,
                page=page.id if page else None,
                ordering=self.ordering,
                is_group_label=self.is_group_label,
                is_active=self.is_active,
                t='item',
            )
        )

    def get_path(self):
        path = self.path or '#'
        return path

    def render(self):
        if self.menu.region == Menu.REGION_NAVBAR:
            return render_template_string("""
                {% if not children %}
                <a href="{{ item.get_path()|default("#") }}">{{ item }}</a>
                {% else %}
                <a href="{{ item.get_path()|default("#") }}"
                   class="dropdown-toggle" data-toggle="dropdown">
                    {{ item }}
                    <b class="caret{% if item.parent_id %} caret-right{% endif %}"></b>
                </a>
                <ul class="dropdown-menu">
                    {% for itm in children.values() %}<li>
                        {{ itm.render()|safe }}
                    </li>
                    {% endfor %}
                </ul>
                {% endif %}
            """, children=self.children, item=self)

    def update(self, data, user_id):
        path = '/%s' % '/'.join([p for p in data.get('path', '').split('/')
                                 if p.strip()])
        name = data.get('name', '').strip()
        assign_page = data.get('assign_page') == 'on'
        page_title = data.get('page_title', '').strip()
        page_slug = slugify(data.get('page_slug', '').strip())
        page_content = data.get('page_content', '').strip()
        is_active = data.get('is_active') and data['is_active'] == 'on'
        if path != self.path:
            self.path = path
        if name and name != self.name:
            self.name = name
        self.is_active = is_active
        if (not self.page_id and assign_page) or self.page_id:
            if not page_title:
                raise ValueError('Page title is required')
            if not page_slug:
                raise ValueError('Page slug is required')
            if not page_content:
                raise ValueError('Page content is required')
        page = None
        if not self.page_id and assign_page:
            page = Page.create(
                created_by_id=user_id, slug=page_slug, title=page_title,
                content=page_content)
        elif self.page_id:
            page = self.page
            is_page_modified = False
            if page_slug != page.slug:
                page.slug = page_slug
                is_page_modified = True
            if page_title != page.title:
                page.title = page_title
                is_page_modified = True
            if page_content != page.content:
                page.content = page_content
                is_page_modified = True
            if is_page_modified:
                page.modified = datetime.now()
                page.modified_by_id = user_id
        if page is not None:
            page.save()
            if not self.page_id:
                self.page_id = page.id
        self.save()

    @classmethod
    def create_item(cls, data, user_id):
        region = data['region']
        menu = Menu.filter_by(region=region).first()
        item = cls(
            menu_id=menu.id, created_by_id=user_id, name=data['name'],
            path=data['path'])
        if int(data['parent']) > 0:
            item.parent_id = data['parent']
        item.update(data, user_id)
        return item


    def __unicode__(self):
        return self.name


class Page(BaseModelMixin, db.Model):
    __tablename__ = 'pages'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    ts = db.Column(db.DateTime, default=datetime.now)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    modified = db.Column(db.DateTime)
    modified_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    menu_item = db.relationship('MenuItem', backref='page', lazy='dynamic')
    slug = db.Column(db.String(255), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)

    def __unicode__(self):
        return self.title

    def to_dict(self, include=None, exclude=None):
        item = self.menu_item.first()
        return dict(
            id=self.id,
            ts=self.ts.isoformat(sep=' ')[:19],
            created_by_id=self.created_by_id,
            modified=self.modified.isoformat(sep=' ')[:19] \
                if self.modified else None,
            modified_by_id=self.modified_by_id,
            menu_item=item.id if item else None,
            slug=self.slug,
            title=self.title,
            content=self.content
        )
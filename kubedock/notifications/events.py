from datetime import datetime
from flask import render_template


USER_CREATED = 1001
USER_CHANGED = 1002
USER_PWD_CHANGED = 1003
USER_PERM_CHANGED = 1004
USER_LOGGEDIN = 1010
# Pod events
POD_CONTAINER_CREATED = 2001
POD_CONTAINER_FAILED = 2002
POD_LIMITS_REACHED = 2003


EVENTS = {
    USER_CREATED: dict(
        name='User created',
        desciption='',
        objects=dict(user=('id', 'username', 'email',),)
    ),
    USER_LOGGEDIN: dict(
        name='User logged in',
        desciption='',
        objects=dict(user=('id', 'username', 'email', '_ts'),)
    ),
    POD_CONTAINER_CREATED: dict(
        name='Pod container created',
        desciption='',
        objects=dict(
            user=('id', 'username', 'email', '_ts'),
            pod=('id', 'name', 'status',),
        )
    ),
    POD_CONTAINER_FAILED: dict(
        name='Pod container failed',
        desciption='',
        objects=dict(
            user=('id', 'username', 'email', '_ts'),
            pod=('id', 'name', 'status',),
        )
    ),
    POD_LIMITS_REACHED: dict(
        name='Pod limits reached',
        desciption='',
        objects=dict(
            user=('id', 'username', 'email', '_ts'),
            pod=('id', 'name', 'status',),
        )
    ),
}


class NotificationException(Exception):
    def __init__(self, msg):
        self.msg = msg


class NotificationEvent(object):
    # User events

    event = None

    def __init__(self, event):
        self.event = event

    @property
    def name(self):
        return EVENTS[self.event]['name']

    @property
    def keys(self):
        return NotificationEvent.get_keys_by_event(self.event)

    def help_text(self):
        return NotificationEvent.help_text_by_event(self.event)

    def get_context_data(self, **kwargs):
        return NotificationEvent.get_context_data_by_event(self.event, **kwargs)

    @classmethod
    def get_keys_by_event(cls, event):
        event_data = EVENTS[event]
        keys = []
        for model, fields in event_data['objects'].items():
            for f in fields:
                if f == '_ts':
                    keys.append('__TS__')
                else:
                    keys.append('__%s_%s__' % (model.upper(), f.upper()))
        return keys

    @classmethod
    def get_events_keys(cls):
        return dict([(e, cls.get_keys_by_event(e)) for e in EVENTS])

    @classmethod
    def get_event_name(cls, event):
        return EVENTS[event]['name']

    @classmethod
    def help_text_by_event(cls, event):
        keys = cls.get_keys(event)
        return render_template('notifications/help_text.html', keys=keys)

    @classmethod
    def get_context_data_by_event(cls, event, **kwargs):
        event_data = EVENTS[event]
        context = {}
        for k, obj in kwargs.items():
            object_fields = event_data['objects'].get(k)
            if object_fields is None:
                continue
            for f in object_fields:
                if f == '_ts':
                    context['__TS__'] = \
                        datetime.now().isoformat(sep=' ')
                else:
                    context['__%s_%s__' % (k.upper(), f.upper())] = getattr(obj, f)
        return context

    @classmethod
    def get_events(cls, exclude=None):
        if isinstance(exclude, (list, tuple)):
            return dict([(e, v['name']) for e, v in EVENTS.items()
                         if e not in exclude])
        return dict([(e, v['name']) for e, v in EVENTS.items()])


    class ModelDoesNotExist(NotificationException):
        pass

    class EventDoesNotExist(NotificationException):
        pass
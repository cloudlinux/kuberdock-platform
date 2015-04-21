from flask import current_app
from flask.ext.mail import Message, Mail
from ..core import db
from ..models_mixin import BaseModelMixin
from ..users.signals import user_logged_in
from ..users.models import User
from .events import NotificationEvent, USER_LOGGEDIN
from .signals import notification_send

## TODO: move send_email_notification(...) function into tasks module
# from ..factory import make_celery
# celery = make_celery()


# @celery.task()
@notification_send.connect
def send_email_notification(args):
    subject, email_to, email_from, text_plain, text_html = args
    if not isinstance(email_to, list):
        email_to = [email_to]
    msg = Message(subject, sender=email_from, recipients=email_to)
    msg.body = text_plain
    msg.html = text_html
    mail = Mail(current_app)
    try:
        mail.send(msg)
    except Exception, e:
        current_app.logger.warning(e)


class NotificationTemplate(BaseModelMixin, db.Model):
    __tablename__ = 'notification_template'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    event = db.Column(db.Integer, nullable=False, unique=True)
    subject = db.Column(db.String(255))
    text_plain = db.Column(db.Text, nullable=False)
    text_html = db.Column(db.Text)
    as_html = db.Column(db.Boolean, default=True, nullable=False)

    @property
    def e(self):
        return NotificationEvent(self.event)

    @property
    def name(self):
        return self.e.name

    def help_text(self):
        return self.e.help_text()

    def to_dict(self, include=None, exclude=None):
        return dict(
            id=self.id,
            event=self.event,
            name=self.name,
            subject=self.subject or 'Subject not defined',
            text_plain=self.text_plain,
            text_html=self.text_html,
            as_html=self.as_html,
            # keys=self.e.keys
        )

    def update(self, data):
        self.subject = data['subject']
        self.text_plain = data['text_plain']
        self.text_html = data['text_html']
        self.as_html = data['as_html']
        self.save()

    def make_templates(self, context):
        subject = self.subject or 'Subject not defined'
        text_plain = self.text_plain
        text_html = self.text_html
        for k, v in context.items():
            if not isinstance(v, basestring):
                v = unicode(v)
            subject = subject.replace(k, v)
            text_plain = text_plain.replace(k, v)
            text_html = text_html.replace(k, v)
        return subject, text_plain, text_html

    @classmethod
    def send_notification(cls, event, **context_data):
        user = context_data['user']
        if not user.email:
            current_app.logger.warning(
                'User "{0}" E-mail not defined'.format(user.username))
            return
        template = cls.filter_by(event=event).first()
        if template is None:
            current_app.logger.warning(
                'Template for event "{0}" does not exist'.format(event))
            return
        context = NotificationEvent.get_context_data_by_event(
            event, **context_data)
        subject, text_plain, text_html = template.make_templates(context)
        ## TODO: define default Flask-Mail config parameters in settings
        email_from = current_app.config.get('DEFAULT_MAIL_SENDER',
                                            'alukyanov@cloudlinux.com')
        notification_send.send((
            subject, user.email, email_from, text_plain, text_html))

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


"""
I'm using simple signal transport 'blinker'.
So, here is the place where your may define additional functionality of the
exist signal, e.g. signal 'user_logged_in', that was defined in
kubedock.users.signals module and connected with actions in
kubedock.users.models module
"""


#####################
### Users signals ###
@user_logged_in.connect
def user_logged_in_signal(args):
    user_id, remote_ip = args
    user = User.filter_by(id=user_id).first()
    context_data = dict(user=user)
    NotificationTemplate.send_notification(USER_LOGGEDIN, **context_data)

from flask import current_app
## TODO: add Flask-Mail into requirements.txt
# from flask.ext.mail import Message, Mail
from ..core import db
from ..models_mixin import BaseModelMixin
from ..users.signals import user_logged_in
from ..users.models import User
from .events import NotificationEvent, USER_LOGGEDIN


## TODO: move send_email_notification(...) function into tasks module
from ..factory import make_celery
celery = make_celery()


@celery.task()
def send_email_notification(subject, email_to, email_from, text_plain,
                            text_html=None):
    print subject
    if not isinstance(email_to, list):
        email_to = [email_to]
    print subject, email_to, email_from
    print text_plain
    print text_html or ''
    # msg = Message(subject, sender=email_from, recipients=email_to)
    # msg.body = text_plain
    # msg.html = text_html
    # mail = Mail(current_app)
    # mail.send(msg)


class NotificationTemplate(BaseModelMixin, db.Model):
    __tablename__ = 'notification_template'

    id = db.Column(
        db.Integer, primary_key=True, autoincrement=True, nullable=False)
    event = db.Column(db.Integer, nullable=False, unique=True)
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
            text_plain=self.text_plain,
            text_html=self.text_html,
            as_html=self.as_html,
            # keys=self.e.keys
        )

    def make_templates(self, context):
        text_plain = self.text_plain
        text_html = self.text_html
        for k, v in context.items():
            if not isinstance(v, basestring):
                v = unicode(v)
            text_plain.replace(k, v)
            text_html.replace(k, v)
        return text_plain, text_html

    @classmethod
    def send_notification(cls, event, **context_data):
        user = context_data['user']
        template = cls.filter_by(event=event).first()
        if template is None:
            return
            # raise Exception(
            #     'Template for event "{0}" does not exist'.format(event))
        context = NotificationEvent.get_context_data_by_event(
            event, **context_data)
        text_plain, text_html = template.make_templates(context)
        subject = 'Subject'
        ## TODO: define default Flask-Mail config parameters in settings
        email_from = current_app.config.get('DEFAULT_MAIL_SENDER',
                                            'alukyanov@cloudlinux.com')
        print email_from
        send_email_notification.delay(subject, user.email, email_from, text_plain,
                                      text_html)

    def __unicode__(self):
        return self.name

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


# FIXME: Must be implemented in users.models
#####################
### Users signals ###
@user_logged_in.connect
def user_logged_in_signal(user_id):
    user = User.filter_by(id=user_id).first()
    context_data = dict(user=user)
    NotificationTemplate.send_notification(USER_LOGGEDIN, **context_data)

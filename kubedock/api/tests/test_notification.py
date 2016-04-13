from kubedock.notifications.events import USER_CREATED, EVENTS
from kubedock.notifications.models import NotificationTemplate
from kubedock.testutils.testcases import APITestCase


class NotificationURL(object):
    list = '/notifications/'.format
    get = '/notifications/{0}'.format
    create = '/notifications/'.format
    put = '/notifications/{0}'.format
    delete = '/notifications/{0}'.format


class TestNotification(APITestCase):
    @staticmethod
    def _create(**kwargs):
        data = {
            'event': USER_CREATED,
            'text_plain': 'text'
        }
        data.update(kwargs)
        return NotificationTemplate.create(**data).save()

    def test_empty_list(self):
        response = self.open(NotificationURL.list())
        self.assert200(response)
        self.assertTrue(len(response.json['data']) == 0)

    def test_list(self):
        map(lambda key: self._create(event=key), EVENTS.keys())
        response = self.open(NotificationURL.list())
        self.assert200(response)
        self.assertTrue(len(response.json['data']) == len(EVENTS.keys()))

    def test_get_not_found(self):
        response = self.open(
            NotificationURL.get(12345))
        self.assertAPIError(response, 404, 'APIError')

    def test_get(self):
        n = self._create()

        response = self.open(NotificationURL.get(n.id))
        self.assert200(response)
        self.assertTrue(response.json['status'] is True)

        new_data = response.json['data']
        self.assertTrue(new_data['text_plain'] == 'text')
        self.assertTrue(new_data['event'] == USER_CREATED)

    def test_create(self):
        response = self.open(
            NotificationURL.create(), 'POST', {
                'event': USER_CREATED,
                'text_plain': 'text',
            })
        self.assert200(response)

    def test_create_invalid(self):
        response = self.open(
            NotificationURL.create(), 'POST', {
                'event': USER_CREATED
            })
        self.assert200(response)  # ??
        self.assertTrue(response.json['status'] != 'OK')

    def test_create_duplicate_event(self):
        self._create()

        # duplicate event
        response = self.open(
            NotificationURL.create(), 'POST', {
                'event': USER_CREATED
            })
        self.assertAPIError(response, 400, 'APIError')

    def test_put_not_found(self):
        response = self.open(NotificationURL.put(1234), 'PUT')
        self.assertAPIError(response, 404, 'APIError')

    def test_put(self):
        n = self._create()
        response = self.open(NotificationURL.put(n.id), 'PUT', {
            'text_plain': 'new text plain',
            'subject': 'new subject',
            'text_html': 'new text html',
            'as_html': True
        })
        self.assert200(response)
        self.assertTrue(response.json['status'] == 'OK')

        response = self.open(NotificationURL.get(n.id))
        self.assert200(response)
        self.assertTrue(response.json['status'] is True)
        new_data = response.json['data']
        self.assertTrue(new_data['text_plain'] == 'new text plain')
        self.assertTrue(new_data['subject'] == 'new subject')
        self.assertTrue(new_data['text_html'] == 'new text html')
        self.assertTrue(new_data['as_html'] is True)

    def test_delete_not_found(self):
        response = self.open(NotificationURL.delete(12345), 'DELETE')
        self.assertAPIError(response, 404, 'APIError')

    def test_delete(self):
        n = self._create()
        response = self.open(NotificationURL.delete(n.id), 'DELETE')
        self.assert200(response)
        self.assertTrue(response.json['status'] == 'OK')
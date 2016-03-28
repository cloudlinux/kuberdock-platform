import unittest
from kubedock.testutils.testcases import APITestCase, attr
from kubedock.testutils import fixtures
from kubedock.system_settings.models import SystemSettings


class TestSystemSettings(APITestCase):
    """
    Test for 'api/settings/sysapi' endpoint
    """
    url = '/settings/sysapi'

    def setUp(self):
        super(TestSystemSettings, self).setUp()
        ss = SystemSettings(name='test_setting',
                            value='test_setting_value',
                            label='test_setting_label',
                            options='["foo", "abc"]',
                            description='test_setting_description',
                            placeholder='test_setting_placeholder')
        fixtures.db.session.add(ss)
        fixtures.db.session.commit()

    @attr('db')
    def test_get_setting(self):
        resp = self.open(self.url, auth=self.adminauth)
        self.assert200(resp)
        # 9 default settings and 1 added in setUp
        self.assertEqual(len(resp.json.get('data')), 9 + 1)
        data = by_name(resp, 'test_setting')
        data.pop('id')  # do not know autoincremented ID
        self.assertEqual(
            {'name': 'test_setting',
             'value': 'test_setting_value',
             'options': ['foo', 'abc'],
             'label': 'test_setting_label',
             'description': 'test_setting_description',
             'placeholder': 'test_setting_placeholder'}, data)

    @attr('db')
    def test_edit_setting(self):
        resp1 = self.open(self.url, auth=self.adminauth)
        self.assert200(resp1)
        sid = by_name(resp1, 'test_setting').get('id')
        json_data = {'value': 'test_setting_edited'}
        resp2 = self.admin_open(self.item_url(sid), 'PATCH', json_data)
        self.assert200(resp2)
        resp3 = self.open(self.url, auth=self.adminauth)
        self.assert200(resp3)
        data = by_name(resp3, 'test_setting')
        data.pop('id', None)  # do not know autoincremented ID
        self.assertEqual(
            {'name': 'test_setting',
             'value': 'test_setting_edited',
             'label': 'test_setting_label',
             'options': ['foo', 'abc'],
             'description': 'test_setting_description',
             'placeholder': 'test_setting_placeholder'}, data)

    @attr('db')
    def test_edit_forbidden_for_user_setting(self):
        resp1 = self.open(self.url, auth=self.adminauth)
        self.assert200(resp1)
        sid = resp1.json.get('data')[0].get('id')
        json_data = {'value': 'test_setting_edited'}
        resp2 = self.open(self.item_url(sid), 'PATCH', json_data,
                          auth=self.userauth)
        self.assert403(resp2)


def by_name(response, name):
    try:
        return (setting for setting in response.json.get('data')
                if setting['name'] == name).next()
    except StopIteration:
        return None


if __name__ == '__main__':
    unittest.main()

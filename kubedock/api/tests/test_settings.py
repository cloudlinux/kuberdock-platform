import unittest
from kubedock.testutils.testcases import APITestCase
from kubedock.system_settings.models import SystemSettings


class TestSystemSettings(APITestCase):
    """
    Test for 'api/settings/sysapi' endpoint
    """
    url = '/settings/sysapi'

    def setUp(self):
        self.setting = SystemSettings(name='test_setting',
                                      value='test_setting_value',
                                      label='test_setting_label',
                                      options='["foo", "abc"]',
                                      description='test_setting_description',
                                      setting_group='test_setting_group',
                                      placeholder='test_setting_placeholder')
        self.db.session.add(self.setting)
        self.db.session.commit()

    def test_get_setting(self):
        resp = self.user_open()
        self.assert200(resp)
        # KD has 4 default public settings
        self.assertEqual(len(resp.json.get('data')), 4)

        # only admin can read private settings
        private_setting_id = SystemSettings.query.filter(
            SystemSettings.name == 'billing_password').value('id')
        resp = self.admin_open(self.item_url(private_setting_id))
        self.assert200(resp)

        # check response format
        resp = self.open(auth=self.adminauth)
        self.assert200(resp)
        # 14 default settings and 1 added in setUp
        self.assertEqual(len(resp.json.get('data')), 14 + 1)
        data = by_name(resp, 'test_setting')
        data.pop('id')  # do not know autoincremented ID
        self.assertEqual(
            {'name': 'test_setting',
             'value': 'test_setting_value',
             'options': ['foo', 'abc'],
             'label': 'test_setting_label',
             'description': 'test_setting_description',
             'setting_group': 'test_setting_group',
             'placeholder': 'test_setting_placeholder'}, data)

    def test_edit_setting(self):
        resp1 = self.open(auth=self.adminauth)
        self.assert200(resp1)
        sid = by_name(resp1, 'test_setting').get('id')
        json_data = {'value': 'test_setting_edited'}
        resp2 = self.admin_open(self.item_url(sid), 'PATCH', json_data)
        self.assert200(resp2)
        resp3 = self.open(auth=self.adminauth)
        self.assert200(resp3)
        data = by_name(resp3, 'test_setting')
        data.pop('id', None)  # do not know autoincremented ID
        self.assertEqual(
            {'name': 'test_setting',
             'value': 'test_setting_edited',
             'label': 'test_setting_label',
             'options': ['foo', 'abc'],
             'description': 'test_setting_description',
             'setting_group': 'test_setting_group',
             'placeholder': 'test_setting_placeholder'}, data)


class TestMisc(APITestCase):
    """
    Test for endpoints:
        api/settings/timezone
        api/settings/timezone-list
        api/settings/menu
        api/settings/notifications
    """
    url = '/settings'

    def test_get_permissions(self):
        """Only users and admins can get menu, notifications, and timezones"""
        timezone_url = '{0}/timezone'.format(self.url)
        self.assert200(self.user_open(timezone_url))
        self.assert200(self.open(timezone_url, auth=self.adminauth))

        timezone_list_url = '{0}/timezone-list'.format(self.url)
        self.assert200(self.user_open(timezone_list_url))
        self.assert200(self.open(timezone_list_url, auth=self.adminauth))

        # TODO: check response data for different roles
        menu_url = '{0}/menu'.format(self.url)
        self.assert200(self.user_open(menu_url))
        self.assert200(self.open(menu_url, auth=self.adminauth))

        # TODO: check response data for different roles
        notifications_url = '{0}/notifications'.format(self.url)
        self.assert200(self.user_open(notifications_url))
        self.assert200(self.open(notifications_url, auth=self.adminauth))


def by_name(response, name):
    try:
        return (setting for setting in response.json.get('data')
                if setting['name'] == name).next()
    except StopIteration:
        return None


if __name__ == '__main__':
    unittest.main()

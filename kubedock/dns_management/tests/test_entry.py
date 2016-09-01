import unittest
import mock

from kubedock.testutils.testcases import FlaskTestCase
from kubedock.testutils import create_app
from kubedock.exceptions import InternalAPIError

from kubedock.dns_management import _entry as entry


class TestCase(FlaskTestCase):
    def create_app(self):
        return create_app(self)


class TestIngressController(TestCase):
    """Tests for kubedock.dns_management._entry._IngressController"""

    def setUp(self):
        patcher = mock.patch.object(entry, '_get_ingress_controller_pod')
        self.get_ingress_controller_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_public_ip(self):
        self.get_ingress_controller_mock.return_value = None
        ingress_controller = entry._IngressController()
        self.assertIsNone(ingress_controller.get_public_ip())

        test_ip = '123.123.123.123'
        pod_mock = mock.Mock()
        pod_mock.get_dbconfig.return_value = test_ip
        self.get_ingress_controller_mock.return_value = pod_mock
        ingress_controller = entry._IngressController()
        self.assertEqual(ingress_controller.get_public_ip(), test_ip)
        # second call must be cached
        self.assertEqual(ingress_controller.get_public_ip(), test_ip)
        pod_mock.get_dbconfig.assert_called_once_with('public_ip')

    def test_is_ready(self):
        self.get_ingress_controller_mock.return_value = None
        ingress_controller = entry._IngressController()
        res, _ = ingress_controller.is_ready()
        self.assertFalse(res)

        pod_mock = mock.Mock()
        pod_mock.get_dbconfig.return_value = None
        self.get_ingress_controller_mock.return_value = pod_mock
        ingress_controller = entry._IngressController()
        res, _ = ingress_controller.is_ready()
        self.assertFalse(res)

        test_ip = '123.123.123.123'
        pod_mock.get_dbconfig.return_value = test_ip
        ingress_controller = entry._IngressController()
        res, _ = ingress_controller.is_ready()
        self.assertTrue(res)


class TestPlugin(TestCase):
    """Tests for kubedock.dns_management._entry._Plugin"""
    def setUp(self):
        patcher = mock.patch.object(entry, 'SystemSettings')
        self.sys_settings_mock = patcher.start()
        self.addCleanup(patcher.stop)

    def test_get_plugin(self):
        self.sys_settings_mock.get_by_name.return_value = 'invalid'
        plugin = entry._Plugin()
        self.assertIsNone(plugin.get_plugin())

        self.sys_settings_mock.get_by_name.return_value = 'example'
        plugin = entry._Plugin()
        plugin_module = plugin.get_plugin()
        self.assertTrue(hasattr(plugin_module.entry, 'delete_type_A_record'))
        self.assertTrue(hasattr(plugin_module.entry,
                                'create_or_update_type_A_record'))

    def test_get_kwargs(self):
        self.sys_settings_mock.get_by_name.return_value = 'invalid'
        plugin = entry._Plugin()
        self.assertIsNone(plugin.get_kwargs())

        self.sys_settings_mock.get_by_name.return_value = 'example'
        plugin = entry._Plugin()
        self.assertEqual(plugin.get_kwargs(), {})

        plugin = entry._Plugin()
        plugin_module = plugin.get_plugin()
        # monkeypatch args in example plugin
        args = ['one', 'two', 'three']
        arg_value = 'qwerty'
        try:
            plugin_module.ALLOWED_ARGS = args
            self.sys_settings_mock.get_by_name.return_value = arg_value
            kwargs = {item: arg_value for item in args}
            self.assertEqual(plugin.get_kwargs(), kwargs)
        finally:
            plugin_module.ALLOWED_ARGS = []
        # check last call to get setting value (last parameter in args)
        self.sys_settings_mock.get_by_name.assert_called_with(
            entry.keys.KEY_PREFIX_DNS_MANAGEMENT + '_example_' + args[-1])

    def test_is_ready(self):
        self.sys_settings_mock.get_by_name.return_value = 'invalid'
        plugin = entry._Plugin()
        res, _ = plugin.is_ready()
        self.assertFalse(res)

        self.sys_settings_mock.get_by_name.return_value = 'example'
        plugin = entry._Plugin()
        res, _ = plugin.is_ready()
        self.assertTrue(res)


class TestFunctions(TestCase):
    """Tests for functions in kubedock.dns_management._entry"""

    @mock.patch.object(entry, '_IngressController')
    @mock.patch.object(entry, '_Plugin')
    def test_is_domain_system_ready(self, plugin_mock, ingress_mock):
        plugin_mock.return_value.is_ready.return_value = (False, '')
        ingress_mock.return_value.is_ready.return_value = (False, '')
        res, _ = entry.is_domain_system_ready()
        self.assertFalse(res)

        plugin_mock.return_value.is_ready.return_value = (True, None)
        ingress_mock.return_value.is_ready.return_value = (False, '')
        res, _ = entry.is_domain_system_ready()
        self.assertFalse(res)

        plugin_mock.return_value.is_ready.return_value = (True, None)
        ingress_mock.return_value.is_ready.return_value = (True, None)
        res, _ = entry.is_domain_system_ready()
        self.assertTrue(res)

    @mock.patch.object(entry, '_IngressController')
    @mock.patch.object(entry, '_Plugin')
    def test_create_or_update_type_A_record(self, plugin_mock, ingress_mock):
        plugin_mock.return_value.is_ready.return_value = (False, '')
        ingress_mock.return_value.is_ready.return_value = (False, '')
        ok, _ = entry.create_or_update_type_A_record('qq')
        self.assertFalse(ok)

        plugin_mock.return_value.is_ready.return_value = (True, None)
        ingress_mock.return_value.is_ready.return_value = (True, None)
        ingress_ip = '123.123.123.111'
        ingress_mock.return_value.get_public_ip.return_value = ingress_ip
        kwargs = {'one': '1', 'two': '2'}
        plugin_mock.return_value.get_kwargs.return_value = kwargs

        domain = 'qwqwqwq'
        ok, _ = entry.create_or_update_type_A_record(domain)
        self.assertTrue(ok)
        plugin_mock.return_value.get_plugin.return_value\
            .entry.create_or_update_type_A_record.assert_called_once_with(
                domain, [ingress_ip], **kwargs)

        plugin_mock.return_value.get_plugin.return_value\
            .entry.create_or_update_type_A_record.side_effect = Exception(
                'fail')
        ok, _ = entry.create_or_update_type_A_record(domain)
        self.assertFalse(ok)

    @mock.patch.object(entry, '_Plugin')
    def test_delete_type_A_record(self, plugin_mock):
        plugin_mock.return_value.is_ready.return_value = (False, '')
        ok, _ = entry.delete_type_A_record('qwerty')
        self.assertFalse(ok)

        plugin_mock.return_value.is_ready.return_value = (True, None)
        kwargs = {'one': '1', 'two': '2'}
        plugin_mock.return_value.get_kwargs.return_value = kwargs
        domain = 'asdfg'
        ok, _ = entry.delete_type_A_record(domain)
        self.assertTrue(ok)
        plugin_mock.return_value.get_plugin.return_value\
            .entry.delete_type_A_record.assert_called_once_with(
                domain, **kwargs)

        plugin_mock.return_value.get_plugin.return_value\
            .entry.delete_type_A_record.side_effect = Exception('fail')
        ok, _ = entry.delete_type_A_record(domain)
        self.assertFalse(ok)


if __name__ == '__main__':
    unittest.main()

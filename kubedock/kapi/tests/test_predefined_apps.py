"""Tests for kapi.predefined_apps
"""
import unittest
import mock


from kubedock.testutils import fixtures
from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi import predefined_apps as kapi_papps


VALID_TEMPLATE1 =\
"""---
apiVersion: v1
kind: ReplicationController
kuberdock:
  icon: http://icons.iconarchive.com/wordpress-icon.png
  kube_type: $KUBETYPE|default:0|Kube type$
  name: Wordpress app
  package_id: 1
  postDescription: Some test %PUBLIC_ADDRESS%
  preDescription: Some pre description
  template_id: 1
metadata:
  labels:
    name: wp
  name: wp
spec:
  template:
    metadata:
      labels:
        name: wp
    spec:
      containers:
        -
          env:
            -
              name: WORDPRESS_DB_NAME
              value: wordpress
            -
              name: WORDPRESS_DB_USER
              value: wordpress
            -
              name: WORDPRESS_DB_PASSWORD
              value: paSd43
            -
              name: WORDPRESS_DB_HOST
              value: 127.0.0.1
            -
              name: WP_ENV1
              value: $WPENV1|default:1|test var 1 1$
            -
              name: WP_ENV2
              value: $WPENV1$
            -
              name: WP_ENV3
              value: $WPENV1$
            -
              name: WP_ENV4
              value: $WPENV1|default:2|test var 1 2$
          image: wordpress
          kubes: $WP_KUBE_COUNT|default:3|Wordpress kubes count$
          name: wordpress
          ports:
            -
              containerPort: 80
              hostPort: 80
          volumeMounts: []

        -
          args: []

          env:
            -
              name: MYSQL_ROOT_PASSWORD
              value: wordpressdocker
            -
              name: MYSQL_DATABASE
              value: wordpress
            -
              name: MYSQL_USER
              value: wordpress
            -
              name: MYSQL_PASSWORD
              value: paSd43
            -
              name: TEST_AUTOGEN1
              value: $TESTAUTO1|default:autogen|test auto1$
          image: mysql
          kubes: $MYSQL_KUBE_COUNT|default:2|MySQL kubes count$
          name: mysql
          ports:
            -
              containerPort: 3306
          volumeMounts: []

      restartPolicy: Always
      volumes: []
"""

INVALID_TEMPLATE_KUBE_TYPE = VALID_TEMPLATE1.replace(
    '$KUBETYPE|default:0', '$KUBETYPE|default:424242'
)


class TestDBAwarePredefinedAppsUtils(DBTestCase):
    """Tests for kapi.predefined_apps wjere database is needed."""
    @mock.patch.object(kapi_papps, 'check_custom_variables')
    def test_validate_template(self, check_vars_mock):
        """Test kapi.predefined_apps.validate_template function"""
        template = VALID_TEMPLATE1
        kapi_papps.validate_template(template)
        check_vars_mock.assert_called_once_with(template)

        template = "some invalid data"
        with self.assertRaises(kapi_papps.APIError):
            kapi_papps.validate_template(template)

        template = INVALID_TEMPLATE_KUBE_TYPE
        with self.assertRaises(kapi_papps.APIError):
            kapi_papps.validate_template(template)


class TestPredefinedAppsUtils(unittest.TestCase):
    """Tests for kapi.predefined_apps wjere database is needed."""

    @mock.patch.object(kapi_papps, 'raise_validation_error')
    def test_check_custom_variables(self, raise_err_mock):
        """Test kapi.predefined_apps.check_custom_variables function"""
        template = "some text $INVALID_VAR$ and $VALID|default:0|description$ ."
        kapi_papps.check_custom_variables(template)
        raise_err_mock.assert_called_once_with('customVars', ['$INVALID_VAR$'])
        raise_err_mock.reset_mock()

        template = "some text $VAR1$ and $VAR1|default:0|description$ ."
        kapi_papps.check_custom_variables(template)
        self.assertFalse(raise_err_mock.called)

        template = "some text $VAR1|default:0|description$, asdfg "\
                   "$VAR2|default:0|description$ zxcv"
        kapi_papps.check_custom_variables(template)
        self.assertFalse(raise_err_mock.called)

    def test_get_value(self):
        """Test kapi.predefined_apps.get_value function"""
        var = "$V1|default:qwerty|asdfg$"
        name, value, title = kapi_papps.get_value(var)
        self.assertEqual(name, 'V1')
        self.assertEqual(value, 'qwerty')
        self.assertEqual(title, 'asdfg')

        var = "$INVALID$"
        name, value, title = kapi_papps.get_value(var)
        self.assertIsNone(name)
        self.assertIsNone(title)
        self.assertEqual(value, var)

        var = "$#$%^$%"
        name, value, title = kapi_papps.get_value(var)
        self.assertIsNone(name)
        self.assertIsNone(title)
        self.assertEqual(value, var)

        with self.assertRaises(kapi_papps.AppParseError):
            kapi_papps.get_value(var, strict=True)

    def test_get_reused_variable_name(self):
        """Test kapi.predefined_apps.get_reused_variable_name function"""
        var = "$some valid variable here$"
        name = kapi_papps.get_reused_variable_name(var)
        self.assertEqual(name, 'some valid variable here')

        var = "qwretrt"
        name = kapi_papps.get_reused_variable_name(var)
        self.assertIsNone(name)

        var = "$this|is not allowed$"
        name = kapi_papps.get_reused_variable_name(var)
        self.assertIsNone(name)


if __name__ == '__main__':
    unittest.main()

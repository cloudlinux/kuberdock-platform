"""Tests for kapi.predefined_apps
"""
import unittest
import mock
import re

from kubedock.testutils.testcases import DBTestCase
from kubedock.kapi import predefined_apps as kapi_papps


VALID_TEMPLATE1 = """---
apiVersion: v1
kind: ReplicationController
kuberdock:
  icon: http://icons.iconarchive.com/wordpress-icon.png
  name: Wordpress app
  packageID: 0
  postDescription: Some \$test %PUBLIC_ADDRESS%
  preDescription: Some pre description
  template_id: 1
  appPackages:
    - name: S
      recommended: yes
      goodFor: up to 100 users
      publicIP: false
      pods:
        - name: $APP_NAME$
          kubeType: 0
          containers:
            - name: mysql
              kubes: 1
            - name: wordpress
              kubes: 2
          persistentDisks:
            - name: wordpress-persistent-storage
              pdSize: 10
            - name: mysql-persistent-storage$VAR_IN_NAME$
              pdSize: $MYSQL_PD_SIZE|default:2|MySQL persistent disk size$
    - name: M
      goodFor: up to 100K visitors
      pods:
        - name: $APP_NAME$
          kubeType: 0
          containers:
            - name: mysql
              kubes: 2
            - name: wordpress
              kubes: 4
          persistentDisks:
            - name: wordpress-persistent-storage
              pdSize: 1
            - name: mysql-persistent-storage$VAR_IN_NAME$
              pdSize: 3
metadata:
  name: $APP_NAME|default:WordPress|App name$
spec:
  template:
    metadata:
      labels:
        name: $APP_NAME$
    spec:
      volumes:
        - name: mysql-persistent-storage$VAR_IN_NAME|default:autogen|v$
          persistentDisk:
            pdName: wordpress_mysql_$PD_RAND|default:autogen|PD rand$
        - name: wordpress-persistent-storage
          persistentDisk:
            pdName: wordpress_www_$PD_RAND$
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
          name: wordpress
          ports:
            -
              containerPort: 80
              hostPort: 80
          volumeMounts:
            - mountPath: /var/www/html
              name: wordpress-persistent-storage

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
          name: mysql
          ports:
            -
              containerPort: 3306
          volumeMounts:
            - mountPath: /var/lib/mysql
              name: mysql-persistent-storage$VAR_IN_NAME$

      restartPolicy: Always
"""

INVALID_TEMPLATE_KUBE_TYPE = VALID_TEMPLATE1.replace('kubeType: 0',
                                                     'kubeType: 424242', 1)
INVALID_TEMPLATE_2_RECOMMENDED = re.sub(r'name: M(\W+)', r'name: M\1recommended: true\1',
                                        VALID_TEMPLATE1, 1)


class TestDBAwarePredefinedAppsUtils(DBTestCase):
    """Tests for kapi.predefined_apps wjere database is needed."""
    @mock.patch.object(kapi_papps, 'check_custom_variables')
    def test_validate_template(self, check_vars_mock):
        """Test kapi.predefined_apps.validate_template function"""
        template = VALID_TEMPLATE1
        kapi_papps.validate_template(template)
        check_vars_mock.assert_called_once_with(template)

        for template in ('some invalid data',
                         INVALID_TEMPLATE_KUBE_TYPE,
                         INVALID_TEMPLATE_2_RECOMMENDED):
            with self.assertRaises(kapi_papps.ValidationError):
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

    def test_parse_fields(self):
        template = """
            some text $VAR_BEFORE_DEFINITION$ and
            $VAR_BEFORE_DEFINITION|default:0|a n % # qwe$ \$
            $AUTOGEN_VAR|default:autogen|rand$ and repeat $AUTOGEN_VAR$
            and repeat $AUTOGEN_VAR$ blah blah
            $WEIRD_CPANEL_STUFF|default:user_domain_list|aa$ $QWERT|default:1|a$
            and repeat $WEIRD_CPANEL_STUFF$ blah
        """
        fields = kapi_papps.parse_fields(template)
        self.assertEqual(fields['VAR_BEFORE_DEFINITION'], {
            'title': 'a n % # qwe', 'value': '0', 'name': 'VAR_BEFORE_DEFINITION',
            'hidden': False, 'occurrences': [
                '$VAR_BEFORE_DEFINITION$',
                '$VAR_BEFORE_DEFINITION|default:0|a n % # qwe$',
            ]
        })
        fields = kapi_papps.parse_fields(template)
        self.assertDictContainsSubset({
            'title': 'rand', 'name': 'AUTOGEN_VAR',
            'hidden': True, 'occurrences': [
                '$AUTOGEN_VAR|default:autogen|rand$',
                '$AUTOGEN_VAR$',
                '$AUTOGEN_VAR$',
            ]
        }, fields['AUTOGEN_VAR'])
        fields = kapi_papps.parse_fields(template)
        self.assertDictContainsSubset({
            'title': 'aa', 'name': 'WEIRD_CPANEL_STUFF',
            'hidden': True, 'occurrences': [
                '$WEIRD_CPANEL_STUFF|default:user_domain_list|aa$',
                '$WEIRD_CPANEL_STUFF$',
            ]
        }, fields['WEIRD_CPANEL_STUFF'])

    def test_get_value(self):
        """Test kapi.predefined_apps.get_value function"""
        var = "$V1|default:qwerty|asdfg$"
        name, value, title = kapi_papps.get_value(var)
        self.assertEqual(name, 'V1')
        self.assertEqual(value, 'qwerty')
        self.assertEqual(title, 'asdfg')

        var = "$INVALID!@#%|^&*$"
        name, value, title = kapi_papps.get_value(var)
        self.assertIsNone(name)
        self.assertIsNone(title)
        self.assertEqual(value, var)

        var = "$REUSED_VAR$"
        self.assertEqual(kapi_papps.get_value(var), (None, var, None))
        self.assertEqual(kapi_papps.get_value(var, with_reused=True),
                         ('REUSED_VAR', None, None))

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

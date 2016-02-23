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


class TestValidateTemplate(DBTestCase):
    """Tests for for kapi.predefined_apps.validate_template"""
    def setUp(self):
        for method in ('preprocess', 'load', 'fill', 'find_root', 'check_plans'):
            patcher = mock.patch.object(kapi_papps, method)
            self.addCleanup(patcher.stop)
            patcher.start()

        kapi_papps.preprocess.return_value = (mock.sentinel.PREPARED_TEMPLATE, mock.sentinel.FIELDS)
        kapi_papps.load.return_value = mock.sentinel.LOADED_TEMPLATE
        kapi_papps.fill.return_value = mock.sentinel.FILLED_TEMPLATE, mock.sentinel.USED_FIELDS

    def test_workflow(self):
        """Check whole workflow (preprocess -> load -> fill -> check semantics)"""
        template = VALID_TEMPLATE1
        self.assertEqual(kapi_papps.validate_template(template), (
            mock.sentinel.USED_FIELDS, mock.sentinel.FILLED_TEMPLATE,
            mock.sentinel.LOADED_TEMPLATE, mock.sentinel.PREPARED_TEMPLATE
        ))
        kapi_papps.preprocess.assert_called_once_with(template, raise_=True)
        kapi_papps.load.assert_called_once_with(mock.sentinel.PREPARED_TEMPLATE,
                                                mock.sentinel.FIELDS)
        kapi_papps.fill.assert_called_once_with(mock.sentinel.LOADED_TEMPLATE,
                                                mock.sentinel.FIELDS)
        kapi_papps.find_root.assert_called_once_with(mock.sentinel.FILLED_TEMPLATE)
        kapi_papps.check_plans.assert_called_once_with(mock.sentinel.FILLED_TEMPLATE)

    def test_preprocess(self):
        """Convert parse errors from preprocess step to validation errors."""
        template = VALID_TEMPLATE1

        kapi_papps.preprocess.side_effect = kapi_papps.AppParseError
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.validate_template(template)

    def test_no_root(self):
        """Raise validation errors if pod's root cannot be found."""
        template = VALID_TEMPLATE1

        kapi_papps.find_root.side_effect = kapi_papps.AppParseError
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.validate_template(template)

    def test_wrong_app_packages(self):
        """Raise validation errors if smth wrong with app packages."""
        template = VALID_TEMPLATE1

        kapi_papps.check_plans.side_effect = kapi_papps.ValidationError
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.validate_template(template)


class TestCheckPlans(DBTestCase):
    """Tests for for kapi.predefined_apps.check_plans"""
    def setUp(self):
        self.prepared_template, self.fields = kapi_papps.preprocess(VALID_TEMPLATE1, raise_=True)
        self.parsed_template = kapi_papps.load(self.prepared_template, self.fields)
        self.filled_template, self.fields = kapi_papps.fill(self.parsed_template, self.fields)

    def test_check_plans_valid(self):
        kapi_papps.check_plans(self.filled_template)

    def test_check_plans_2_recommended(self):
        self.filled_template['kuberdock']['appPackages'][1]['recommended'] = True
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.check_plans(self.filled_template)

    def test_check_plans_unknown_pod(self):
        self.filled_template['kuberdock']['appPackages'][0]['pods'][0]['name'] = 'invalid'
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.check_plans(self.filled_template)

    def test_check_plans_unknown_container(self):
        self.filled_template['kuberdock']['appPackages'][0]['pods'][0]\
            ['containers'][0]['name'] = 'invalid'
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.check_plans(self.filled_template)

    def test_check_plans_unknown_pd(self):
        self.filled_template['kuberdock']['appPackages'][0]['pods'][0]\
            ['persistentDisks'][0]['name'] = 'invalid'
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.check_plans(self.filled_template)

    def test_check_plans_invalid_kube_type(self):
        self.filled_template['kuberdock']['appPackages'][0]['pods'][0]['kubeType'] = -1
        with self.assertRaises(kapi_papps.ValidationError):
            kapi_papps.check_plans(self.filled_template)


class TestPreprocess(unittest.TestCase):
    """Tests for for kapi.predefined_apps.preprocess"""
    def test_escaping(self):
        template, fields = kapi_papps.preprocess("""
        $VAR|default:0|yea$
        $$NOT_VAR|default:0|nope$$
        $$$VAR_IN_DOLLARS|default:0|wow$$$
        """, raise_=True)

        self.assertEqual(set(fields.keys()), set(['VAR', 'VAR_IN_DOLLARS']))
        self.assertEqual(template, """
        {0}
        $NOT_VAR|default:0|nope$
        ${1}$
        """.format(fields['VAR'].uid, fields['VAR_IN_DOLLARS'].uid))

    def test_second_definition(self):
        template, fields = kapi_papps.preprocess("""
        $VAR|default:0|yea$
        $VAR|default:1|nope$
        """, raise_=True)
        self.assertEqual(fields['VAR'].label, 'yea')

    def test_undefinined_field_error(self):
        with self.assertRaises(kapi_papps.AppParseError):
            template, fields = kapi_papps.preprocess('$VAR$', raise_=True)

        template, fields = kapi_papps.preprocess(
            '$VAR$ $VAR|default:0|just defined later$', raise_=True)


class TestLoad(unittest.TestCase):
    """Tests for for kapi.predefined_apps.load"""
    def test_load(self):
        fields = {
            'VAR_1': kapi_papps.TemplateField('VAR_1', '0', 'first var label'),
            'VAR_2': kapi_papps.TemplateField('VAR_2', '0', 'second var label'),
        }

        template = kapi_papps.load("""
        a: {0}
        b: just some string
        c:
          - d: |
              string with {1}
            e: {1}
        """.format(fields['VAR_1'].uid, fields['VAR_2'].uid), fields)

        # All UID that are plain YAML-scalars must be replaced with appropriate
        # TemplateField instace. All UID's inside strings must be left as-is.
        self.assertEqual(template, {
            'a': fields['VAR_1'],
            'b': 'just some string',
            'c': [{
                'd': 'string with {0}\n'.format(fields['VAR_2'].uid),
                'e': fields['VAR_2'],
            }],
        })


class TestFill(unittest.TestCase):
    """Tests for for kapi.predefined_apps.fill"""
    def test_fill(self):
        fields = {
            'VAR_1': kapi_papps.TemplateField('VAR_1', 'default-1', 'first var label'),
            'VAR_2': kapi_papps.TemplateField('VAR_2', 'default-2', 'second var label'),
            'VAR_3': kapi_papps.TemplateField('VAR_3', 'default-2', 'third var label'),
        }
        template = {
            'a': fields['VAR_1'],
            'b': 'just some string',
            'c': [{
                'd': 'string with {0}\n'.format(fields['VAR_2'].uid),
                'e': fields['VAR_2'],
            }],
        }

        filled_template, used_fields = kapi_papps.fill(template, fields)
        self.assertEqual(filled_template, {
            'a': 'default-1',
            'b': 'just some string',
            'c': [{
                'd': 'string with default-2\n',
                'e': 'default-2',
            }],
        })
        self.assertEqual(used_fields, {field.name: field for field in fields.itervalues()
                                       if field.name != 'VAR_3'})


if __name__ == '__main__':
    unittest.main()

import json
import logging
import sys
import time
import re
from urlparse import urlparse

import memcache
import pymongo
import redis


from pg import DB

from tests_integration.lib.exceptions import WrongCLICommand
from tests_integration.lib.pod import KDPod
from tests_integration.lib.pod import DEFAULT_WAIT_PORTS_TIMEOUT
from tests_integration.lib.utils import \
    assert_eq, assert_in, kube_type_to_int, \
    kube_type_to_str, get_rnd_string

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger("paramiko").setLevel(logging.WARNING)
LOG = logging.getLogger(__name__)


class KDPAPod(KDPod):
    def __init__(self, cluster, pod_name, plan_id, kube_type, restart_policy,
                 owner):
        self.cluster = cluster
        self.name = pod_name
        self.plan_id = plan_id
        self.owner = owner
        self.open_all_ports = True
        self.kube_type = kube_type
        self.restart_policy = restart_policy

    @classmethod
    def create(cls, cluster, template_name, plan_id, owner, command,
               rnd_str, pod_name=None):
        commands = {
            "kcli2": cluster.kcli2,
            "kdctl": cluster.kdctl
        }
        if command not in commands:
            raise WrongCLICommand("Only kcli2 and kdctl tools can be used for "
                                  "creation of new pod, however '{}' is used".
                                  format(command))
        pa_data = cluster.pas.get_by_name(template_name)
        pa_id = pa_data['id']

        if not pod_name:
            pod_name = template_name + get_rnd_string(prefix="_")

        data = json.dumps({'PD_RAND': rnd_str,
                           'APP_NAME': pod_name})

        base_command = "predefined-apps create-pod {} {} '{}'".format(
            pa_id, plan_id, data)

        if command == "kdctl":
            _, pod_description, _ = commands[command](
                "{} --owner {}".format(base_command, owner),
                out_as_dict=True)
        elif command == "kcli2":
            _, pod_description, _ = commands[command](
                base_command, user=owner,
                out_as_dict=True)

        data = pod_description['data']
        pod_name = data['name']
        kube_type = kube_type_to_str(data['kube_type'])
        restart_policy = data['restartPolicy']
        this_pod_class = cls._get_pod_class(template_name)
        return this_pod_class(cluster, pod_name, plan_id, kube_type,
                              restart_policy, owner)

    def _generic_healthcheck(self):
        spec = self.get_spec()
        assert_eq(spec['kube_type'], kube_type_to_int(self.kube_type))
        assert_eq(spec['restartPolicy'], self.restart_policy)
        assert_eq(spec['status'], "running")
        return spec


class _RedisPaPod(KDPAPod):
    SRC = 'redis.yaml'

    def healthcheck(self):
        spec = self._generic_healthcheck()
        assert_eq(len(spec['containers']), 1)
        assert_eq(spec['containers'][0]['image'], 'redis:3')
        r = redis.StrictRedis(host=self.host, port=6379, db=0)
        r.set('foo', 'bar')
        assert_eq(r.get('foo'), 'bar')


class _RedisCustomPaPod(_RedisPaPod):
    SRC = 'custom_redis.yaml'


class _DokuwikiPaPod(KDPAPod):
    SRC = 'dokuwiki.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        assert_in("Welcome to your new DokuWiki",
                  self.do_GET(path='/doku.php?id=wiki:welcome'))


class _DrupalPaPod(KDPAPod):
    SRC = 'drupal.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        # Change assertion string after fix AC-4487
        page = self.do_GET(path='/core/install.php')
        assert_in("Drupal", page)


class _ElasticsearchPaPod(KDPAPod):
    SRC = 'elasticsearch.yaml'

    def wait_for_ports(self):
        "Elastic PA isn't listen public ip"
        pass

    def healthcheck(self):
        self._generic_healthcheck()


class _RedminePaPods(KDPAPod):
    SRC = 'redmine.yaml'
    HTTP_PORT = 3000

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        assert_in("Redmine", self.do_GET(port=self.HTTP_PORT))


class _JoomlaPaPod(KDPAPod):
    SRC = 'joomla.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/installation/index.php')
        assert_in(u"Joomla! - Open Source Content Management", page)


class _MemcachedPaPod(KDPAPod):
    SRC = 'memcached.yaml'

    def healthcheck(self):
        spec = self._generic_healthcheck()
        assert_eq(len(spec['containers']), 1)
        assert_eq(spec['containers'][0]['image'], 'memcached:1')
        mc = memcache.Client(['{host}:11211'.format(host=self.host)],
                             debug=0)
        mc.set("foo", "bar")
        assert_eq(mc.get("foo"), "bar")


class _Gallery3PaPod(KDPAPod):
    SRC = 'gallery3.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/installer/')
        assert_in(u"Installing Gallery is easy.  "
                  "We just need a place to put your photos", page)


class _MagentoPaPod(KDPAPod):
    SRC = 'magento.yaml'
    WAIT_PORTS_TIMEOUT = 60 * 10

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/index.php/install/')
        assert_in(u"Magento is a trademark of Magento Inc.", page)


class _MantisPaPod(KDPAPod):
    SRC = 'mantis.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/admin/install.php')
        assert_in(u"Administration - Installation - MantisBT", page)


class _MybbPaPod(KDPAPod):
    SRC = 'mybb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"MyBB Installation Wizard", page)


class _OpenCartPaPod(KDPAPod):
    SRC = 'opencart.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"Please read the OpenCart licence agreement", page)


class _LimesurveyPaPod(KDPAPod):
    SRC = 'limesurvey.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/index.php?r=installer/welcome')
        assert_in(u"LimeSurvey installer", page)


class _KokenPaPod(KDPAPod):
    SRC = 'koken.yaml'
    WAIT_PORTS_TIMEOUT = 60 * 10

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET()
        assert_in(u"Koken - Setup", page)


class _OwnCloudPaPod(KDPAPod):
    SRC = 'owncloud.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET()
        assert_in(u"ownCloud", page)
        assert_in(u"web services under your control", page)


class _PhpBBPaPod(KDPAPod):
    SRC = 'phpbb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"Welcome to phpBB3!", page)


class _WordpressPaPod(KDPAPod):
    SRC = 'wordpress.yaml'
    WAIT_PORTS_TIMEOUT = 60 * 10
    _installed = False

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)

    def gen_workload(self, load_time):
        self.pass_install()
        opener = self.get_wp_opener()

        t0 = time.time() + load_time
        while t0 > time.time():
            self.publish_post(opener)
            time.sleep(1)

    def pass_install(self):
        if self._installed:
            return
        body = {
            'weblog_title': 'test',
            'user_name': 'test',
            'admin_password': 'tes_t123',
            'admin_password2': 'tes_t123',
            'admin_email': 'test@test.test',
            'language': 'en_GB'
        }
        self.do_POST(path='/wp-admin/install.php?step=2', body=body,
                     timeout=15, verbose=False)
        self._installed = True

    def get_wp_opener(self):
        return self.get_opener(path='/wp-login.php', body={
            "log": 'test',
            'pwd': 'tes_t123'
        })

    def publish_post(self, content=None, opener=None):
        self.pass_install()

        if not content:
            content = get_rnd_string(100, prefix="Random Content: ")
        if not opener:
            opener = self.get_wp_opener()

        resp = self.do_POST(path='/wp-admin/post-new.php',
                            opener=opener, timeout=10, verbose=False)
        # TODO use BS
        nonce = re.search(
            'name="_wpnonce" value="([a-z0-9]+)"', resp).group(1)
        post_id = re.search(
            "name='post_ID' value='([a-z0-9]+)'", resp).group(1)
        body = {
            "_wpnonce": nonce,
            "post_title": "Post_{}".format(time.time()),
            "user_ID": "1",
            "post_author": "1",
            "post_type": "post",
            "content": content,
            "visibility": "public",
            "action": "editpost",
            "post_ID": post_id,
            "post_author_override": "1",
            "publish": "Publish"
        }
        resp = self.do_POST(path='/wp-admin/post.php', body=body,
                            opener=opener, timeout=10, verbose=False)
        post_url = re.search(
            'Post published. <a href="([^"]*)"', resp).group(1)
        return urlparse(post_url).path


class _PhpMyAdminPaPod(KDPAPod):
    SRC = 'phpmyadmin.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/server_databases.php')
        assert_in(u"information_schema", page)
        assert_in(u"mydata", page)


class _SugarCrmPaPod(KDPAPod):
    SRC = 'sugarcrm.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/install.php')
        assert_in(u"Sugar Setup Wizard:", page)
        assert_in(u"Welcome to the SugarCRM", page)


class _PostgresPaPod(KDPAPod):
    SRC = 'postgres.yaml'
    WAIT_PORTS_TIMEOUT = 60 * 10

    def healthcheck(self):
        self._generic_healthcheck()
        spec = self.get_spec()
        env = {e['name']: e['value'] for e in spec['containers'][0]['env']}
        user = env['POSTGRES_USER']
        passwd = env['POSTGRES_PASSWORD']
        db = DB(dbname=user, host=self.host, port=5432,
                user=user, passwd=passwd)
        sql = "create table test_table(id serial primary key, name varchar)"
        db.query(sql)
        assert_in('public.test_table', db.get_tables())


class _MongodbPaPod(KDPAPod):
    SRC = 'mongodb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        mongo = pymongo.MongoClient(self.host, 27017)
        test_db = mongo.test_db
        assert_eq(u'test_db', test_db.name)
        obj_id = test_db.test_collection.insert_one({"x": 1}).inserted_id
        obj = test_db.test_collection.find_one()
        assert_eq(obj_id, obj['_id'])
        assert_eq(1, obj['x'])


class _OdooPaPod(KDPAPod):
    SRC = 'odoo.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_PORTS_TIMEOUT):
        # Though odoo also has ssl port 8071
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/web/database/selector')
        assert_in(u"Fill in this form to create an Odoo database.", page)


class _WordpressElasticPaPod(KDPAPod):
    SRC = 'wordpress_elasticsearch.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)


class _WordpressBackupPaPod(KDPAPod):
    SRC = 'wordpress_with_backup.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        self.wait_http_resp()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)

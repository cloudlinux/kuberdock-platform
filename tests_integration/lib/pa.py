import json
import redis
import memcache
import pymongo

from pg import DB

from tests_integration.lib.pod import KDPod
from tests_integration.lib.pod import DEFAULT_WAIT_POD_TIMEOUT
from tests_integration.lib.integration_test_utils import \
    assert_eq, assert_in, kube_type_to_int, \
    kube_type_to_str


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
    def create(cls, cluster, template_name, plan_id, owner, rnd_str=None):

        pa_data = cluster.pas.get_by_name(template_name)
        pa_id = pa_data['id']
        data = json.dumps({'PD_RAND': rnd_str or 'test_data_random'})
        _, pod_description, _ = cluster.kcli2(
            "predefined-apps create-pod {} {} '{}'".format(
                pa_id, plan_id, data),
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
        r = redis.StrictRedis(host=self.public_ip, port=6379, db=0)
        r.set('foo', 'bar')
        assert_eq(r.get('foo'), 'bar')


class _DokuwikiPaPod(KDPAPod):
    SRC = 'dokuwiki.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        assert_in("Welcome to your new DokuWiki",
                  self.do_GET(path='/doku.php?id=wiki:welcome'))


class _DrupalPaPod(KDPAPod):
    SRC = 'drupal.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
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

    def healthcheck(self):
        self._generic_healthcheck()
        assert_in("Redmine", self.do_GET())


class _JoomlaPaPod(KDPAPod):
    SRC = 'joomla.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/installation/index.php')
        assert_in(u"Joomla! - Open Source Content Management", page)


class _MemcachedPaPod(KDPAPod):
    SRC = 'memcached.yaml'

    def healthcheck(self):
        spec = self._generic_healthcheck()
        assert_eq(len(spec['containers']), 1)
        assert_eq(spec['containers'][0]['image'], 'memcached:1')
        mc = memcache.Client(['{host}:11211'.format(host=self.public_ip)],
                             debug=0)
        mc.set("foo", "bar")
        assert_eq(mc.get("foo"), "bar")


class _Gallery3PaPod(KDPAPod):
    SRC = 'gallery3.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/installer/')
        assert_in(u"Installing Gallery is easy.  "
                  "We just need a place to put your photos", page)


class _MagentoPaPod(KDPAPod):
    SRC = 'magento.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/index.php/install/')
        assert_in(u"Magento is a trademark of Magento Inc.", page)


class _MantisPaPod(KDPAPod):
    SRC = 'mantis.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/admin/install.php')
        assert_in(u"Administration - Installation - MantisBT", page)


class _MybbPaPod(KDPAPod):
    SRC = 'mybb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"MyBB Installation Wizard", page)


class _OpenCartPaPod(KDPAPod):
    SRC = 'opencart.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"Please read the OpenCart licence agreement", page)


class _LimesurveyPaPod(KDPAPod):
    SRC = 'limesurvey.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/index.php?r=installer/welcome')
        assert_in(u"LimeSurvey installer", page)


class _KokenPaPod(KDPAPod):
    SRC = 'koken.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET()
        assert_in(u"Koken - Setup", page)


class _OwnCloudPaPod(KDPAPod):
    SRC = 'owncloud.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET()
        assert_in(u"ownCloud", page)
        assert_in(u"web services under your control", page)


class _PhpBBPaPod(KDPAPod):
    SRC = 'phpbb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/install/index.php')
        assert_in(u"Welcome to phpBB3!", page)


class _WordpressPaPod(KDPAPod):
    SRC = 'wordpress.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)


class _PhpMyAdminPaPod(KDPAPod):
    SRC = 'phpmyadmin.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/server_databases.php')
        assert_in(u"information_schema", page)
        assert_in(u"mydata", page)


class _SugarCrmPaPod(KDPAPod):
    SRC = 'sugarcrm.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/install.php')
        assert_in(u"Sugar Setup Wizard:", page)
        assert_in(u"Welcome to the SugarCRM", page)


class _PostgresPaPod(KDPAPod):
    SRC = 'postgres.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        spec = self.get_spec()
        env = {e['name']: e['value'] for e in spec['containers'][0]['env']}
        user = env['POSTGRES_USER']
        passwd = env['POSTGRES_PASSWORD']
        db = DB(dbname=user, host=self.public_ip, port=5432,
                user=user, passwd=passwd)
        sql = "create table test_table(id serial primary key, name varchar)"
        db.query(sql)
        assert_in('public.test_table', db.get_tables())


class _MongodbPaPod(KDPAPod):
    SRC = 'mongodb.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        mongo = pymongo.MongoClient(self.public_ip, 27017)
        test_db = mongo.test_db
        assert_eq(u'test_db', test_db.name)
        obj_id = test_db.test_collection.insert_one({"x": 1}).inserted_id
        obj = test_db.test_collection.find_one()
        assert_eq(obj_id, obj['_id'])
        assert_eq(1, obj['x'])


class _OdooPaPod(KDPAPod):
    SRC = 'odoo.yaml'

    def wait_for_ports(self, ports=None, timeout=DEFAULT_WAIT_POD_TIMEOUT):
        # Though odoo also has ssl port 8071
        ports = ports or [80]
        self._wait_for_ports(ports, timeout)

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/web/database/selector')
        assert_in(u"Fill in this form to create an Odoo database.", page)


class _WordpressElasticPaPod(KDPAPod):
    SRC = 'wordpress_elasticsearch.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)


class _WordpressBackupPaPod(KDPAPod):
    SRC = 'wordpress_with_backup.yaml'

    def healthcheck(self):
        self._generic_healthcheck()
        page = self.do_GET(path='/wp-admin/install.php')
        assert_in(u"WordPress &rsaquo; Installation", page)


from tests_integration.lib.pipelines import pipeline


def check_pa(cluster, template_name):
    cluster.pods.create_pa(template_name, wait_ports=True,
                           wait_for_status='running',
                           healthcheck=True)


@pipeline('predefined_apps')
def test_redis_pa(cluster):
    check_pa(cluster, 'redis.yaml')


@pipeline('predefined_apps')
def test_dokuwiki_pa(cluster):
    check_pa(cluster, 'dokuwiki.yaml')


@pipeline('predefined_apps')
def test_drupal_pa(cluster):
    check_pa(cluster, 'drupal.yaml')


@pipeline('predefined_apps')
def test_elasticsearch_pa(cluster):
    check_pa(cluster, 'elasticsearch.yaml')


# Uncomment after AC-4615
# @pipeline('predefined_apps')
def test_redmine_pa(cluster):
    check_pa(cluster, 'redmine.yaml')


@pipeline('predefined_apps')
def test_joomla_pa(cluster):
    check_pa(cluster, 'joomla.yaml')


@pipeline('predefined_apps')
def test_memcached_pa(cluster):
    check_pa(cluster, 'memcached.yaml')

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


@pipeline('predefined_apps')
def test_gallery_pa(cluster):
    check_pa(cluster, 'gallery3.yaml')


@pipeline('predefined_apps')
def test_magento_pa(cluster):
    check_pa(cluster, 'magento.yaml')


@pipeline('predefined_apps')
def test_mantis_pa(cluster):
    check_pa(cluster, 'mantis.yaml')


@pipeline('predefined_apps')
def test_mybb_pa(cluster):
    check_pa(cluster, 'mybb.yaml')


@pipeline('predefined_apps')
def test_opencart_pa(cluster):
    check_pa(cluster, 'opencart.yaml')


@pipeline('predefined_apps')
def test_limesurvey_pa(cluster):
    check_pa(cluster, 'limesurvey.yaml')


@pipeline('predefined_apps')
def test_koken_pa(cluster):
    check_pa(cluster, 'koken.yaml')


@pipeline('predefined_apps')
def test_owncloud_pa(cluster):
    check_pa(cluster, 'owncloud.yaml')


@pipeline('predefined_apps')
def test_phpbb_pa(cluster):
    check_pa(cluster, 'phpbb.yaml')


@pipeline('predefined_apps')
def test_wordpress_pa(cluster):
    check_pa(cluster, 'wordpress.yaml')

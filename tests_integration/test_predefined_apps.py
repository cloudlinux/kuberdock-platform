
# KuberDock - is a platform that allows users to run applications using Docker
# container images and create SaaS / PaaS based on these applications.
# Copyright (C) 2017 Cloud Linux INC
#
# This file is part of KuberDock.
#
# KuberDock is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# KuberDock is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with KuberDock; if not, see <http://www.gnu.org/licenses/>.

from tests_integration.lib.utils import assert_eq
from tests_integration.lib.pipelines import pipeline


def check_pa(cluster, template_name):
    cluster.pods.create_pa(template_name, wait_ports=True,
                           wait_for_status='running',
                           healthcheck=True)


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_redis_pa(cluster):
    check_pa(cluster, 'redis.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_dokuwiki_pa(cluster):
    check_pa(cluster, 'dokuwiki.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_drupal_pa(cluster):
    check_pa(cluster, 'drupal.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_elasticsearch_pa(cluster):
    check_pa(cluster, 'elasticsearch.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_redmine_pa(cluster):
    check_pa(cluster, 'redmine.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_joomla_pa(cluster):
    check_pa(cluster, 'joomla.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_memcached_pa(cluster):
    check_pa(cluster, 'memcached.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_gallery_pa(cluster):
    check_pa(cluster, 'gallery3.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_magento_pa(cluster):
    check_pa(cluster, 'magento.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_mantis_pa(cluster):
    check_pa(cluster, 'mantis.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_mybb_pa(cluster):
    check_pa(cluster, 'mybb.yaml')


@pipeline('predefined_apps')
@pipeline('predefined_apps_aws')
def test_opencart_pa(cluster):
    check_pa(cluster, 'opencart.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_limesurvey_pa(cluster):
    check_pa(cluster, 'limesurvey.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_koken_pa(cluster):
    check_pa(cluster, 'koken.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_owncloud_pa(cluster):
    check_pa(cluster, 'owncloud.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_phpbb_pa(cluster):
    check_pa(cluster, 'phpbb.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_wordpress_pa(cluster):
    check_pa(cluster, 'wordpress.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_phpmysqladmin_pa(cluster):
    check_pa(cluster, 'phpmyadmin.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_sugarcrm_pa(cluster):
    check_pa(cluster, 'sugarcrm.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_postgres_pa(cluster):
    check_pa(cluster, 'postgres.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_mongodb_pa(cluster):
    check_pa(cluster, 'mongodb.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_odoo_pa(cluster):
    check_pa(cluster, 'odoo.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_wordpresselastic_pa(cluster):
    check_pa(cluster, 'wordpress_elasticsearch.yaml')


@pipeline('predefined_apps', thread=2)
@pipeline('predefined_apps_aws')
def test_wordpressbackup_pa(cluster):
    check_pa(cluster, 'wordpress_with_backup.yaml')


@pipeline('kubetype')
def test_redis_pa_tiny(cluster):
    pod = cluster.pods.create_pa('custom_redis.yaml', plan_id=0,
                                 wait_ports=True,
                                 wait_for_status='running',
                                 healthcheck=True)
    spec = pod.get_spec()
    assert_eq(spec['containers'][0]['kubes'], 1)


@pipeline('kubetype')
def test_redis_pa_standard(cluster):
    pod = cluster.pods.create_pa('custom_redis.yaml', plan_id=1,
                                 wait_ports=True,
                                 wait_for_status='running',
                                 healthcheck=True)
    spec = pod.get_spec()
    assert_eq(spec['containers'][0]['kubes'], 2)


@pipeline('kubetype')
def test_redis_pa_highmem(cluster):
    pod = cluster.pods.create_pa('custom_redis.yaml', plan_id=2,
                                 wait_ports=True,
                                 wait_for_status='running',
                                 healthcheck=True)
    spec = pod.get_spec()
    assert_eq(spec['containers'][0]['kubes'], 4)

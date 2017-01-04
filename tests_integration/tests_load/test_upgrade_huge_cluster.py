
from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import log_debug, log_info, assert_eq, \
    wait_pods_status


@pipeline('huge_cluster_upgrade')
@pipeline('huge_cluster_upgrade_aws')
def test_upgrade_huge_cluster(cluster):
    USERS = 15
    PODS_PER_USER = 10
    # Create a lot of users - for first try 5000,
    #    in future we can increase this number
    # Create a lot of pods - 10 per user
    # Upgrade KD

    log_info("Start creating of {} users".format(USERS))
    users = create_users(cluster,
                         {'user_name': 'int_test_user_{num}',
                          'user_email_domain': "example.com"},
                         USERS)  # Increase after debug to 5000
    log_debug(users)
    all_users = cluster.users.get_kd_users()
    assert_eq(len(users), USERS)
    assert_eq(len([u for u in all_users if 'int_test_user_' in u]), USERS)
    log_info("Start creating pods {} for each users".format(PODS_PER_USER))
    pods = []
    for user in users:
        for n in range(PODS_PER_USER):
            pod = cluster.pods.create('histrio/webhook:v1',
                                      '{user}_webhook_{n}'.format(
                                          user=user['username'],
                                          n=n),
                                      kube_type="Tiny",
                                      owner=user['username'])
            pods.append(pod)
    log_debug(pods)
    log_info('Waiting while all pods will be running')
    wait_pods_status(pods, 'running')
    log_info("Starting upgrade kuberdock")
    cluster.upgrade('/tmp/prebuilt_rpms/kuberdock.rpm',
                    use_testing=True, skip_healthcheck=True)
    wait_pods_status(pods, 'running')


def create_users(cluster, user_tempale, user_count):
    ret = []
    for i in range(user_count):
        name = user_tempale['user_name'].format(num=i)
        email = '{name}@{domain}'.format(
            name=name,
            domain=user_tempale['user_email_domain'])
        cluster.users.create(name=name, password=name, email=email)
        user = cluster.users.get(name=name)
        ret.append(user)

    return ret

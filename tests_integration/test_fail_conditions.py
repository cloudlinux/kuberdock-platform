from time import sleep
from tests_integration.lib.pipelines import pipeline


@pipeline('fail_conditions')
def test_resume_halt_host(cluster):
    cluster.power_off('node1')
    sleep(60)
    cluster.power_on('node1')
    cluster.ssh_exec('node1', "echo 'hello world'", check_retcode=True)

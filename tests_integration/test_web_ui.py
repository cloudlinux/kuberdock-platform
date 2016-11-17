from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import local_exec


@pipeline('web_ui')
@pipeline('web_ui_aws')
def test_web_ui(cluster):
    master_ip = cluster.get_host_ip("master")
    env = {
        'ROBOT_ARGS': (" -v SERVER:{0}"
                       " -v ADMIN_PASSWORD:admin"
                       # " -v BROWSER:firefox"
                       " /tests").format(master_ip)
    }
    local_exec(["tox", "-e", "webui"], env)

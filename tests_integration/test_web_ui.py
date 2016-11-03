from tests_integration.lib.pipelines import pipeline
from tests_integration.lib.utils import local_exec


@pipeline('web_ui')
def test_web_ui(cluster):
    env = {
        'ROBOT_ARGS': (" -v SERVER:{0}"
                       " -v ADMIN_PASSWORD:admin"
                       # " -v BROWSER:firefox"
                       " /tests").format(cluster.get_host_ip("master"))
    }
    local_exec(["tox", "-e", "webui"], env)

from tests_integration.lib.pipelines import pipeline


@pipeline('predefined_apps')
def test_add_run_delete_pa(cluster):
    """
    Testing workflow of PA's
    """
    pa_test = "dokuwiki_test"

    # Add PA to list of PA's
    cluster.pas.add(name=pa_test,
                    file_path="/tmp/kuberdock_predefined_apps/dokuwiki.yaml")

    pa_id = cluster.pas.get_by_name(pa_test)['id']

    # Create pod and delete PA from list
    cluster.pods.create_pa(template_name=pa_test, plan_id=1)
    cluster.pas.delete(pa_id)

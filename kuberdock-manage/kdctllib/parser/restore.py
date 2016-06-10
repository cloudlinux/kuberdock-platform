import click

from main import main
from utils import data_argument


@main.group(help='Restore objects from backups.')
def restore():
    pass


@restore.command(help='Restore pod.')
@data_argument('pod-data')
@click.option('--owner')
@click.option('--volumes-dir-url')
@click.pass_obj
def pod(obj, pod_data, owner, volumes_dir_url):
    return obj.client.restore.pod(pod_data, owner, volumes_dir_url)

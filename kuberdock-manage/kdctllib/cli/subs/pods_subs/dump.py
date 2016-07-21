import json
import os

from ... import kdclick
from ...utils import file_utils


@kdclick.command()
@kdclick.argument('pod-id')
@kdclick.pass_obj
def dump(obj, **params):
    return obj.executor.dump(**params)


@kdclick.command('batch-dump')
@kdclick.option('--owner', required=False,
                help='If specified, only pods of this user will be dumped')
@kdclick.option('--target-dir', required=False,
                type=kdclick.Path(dir_okay=True, file_okay=False,
                                  resolve_path=True),
                help='If specified, pod dumps will be saved there '
                     'in the following structure: '
                     '<target_dir>/<owner_id>/<pod_id>')
@kdclick.pass_obj
def batch_dump(obj, owner=None, target_dir=None):
    result = obj.executor.batch_dump(owner)
    if target_dir is None:
        return result
    else:
        dumps = result['data']
        if dumps is None:
            dumps = []
        _save_batch_dump_result(obj, dumps, target_dir)


def _save_batch_dump_result(obj, dumps, target_dir):
    """Saves dumps to <target_dir>/<owner_id>/<pod_id>"""
    for dump in dumps:
        owner_id = dump['owner']['id']
        pod_id = dump['pod_data']['id']
        target_dir0 = os.path.join(target_dir, str(owner_id))
        file_utils.ensure_dir(target_dir0)
        target_file = os.path.join(target_dir0, str(pod_id))
        with open(target_file, 'w') as f:
            json.dump(dump, f, indent=4, sort_keys=True)
        obj.io.out_text('Saved %s' % target_file)

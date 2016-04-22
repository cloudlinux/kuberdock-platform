import random
import string

from flask import current_app

from ..exceptions import APIError


def raise_(message, code=409):
    raise APIError(message, status_code=code)


def _format_msg(error, message, return_value):
    msg = error
    if message:
        msg = u'({}){}'.format(error, message)
    return u'{}: {}'.format(msg, unicode(return_value))


def raise_if_failure(return_value, message=None):
    """
    Raises error if return value has key 'status' and that status' value
    neither 'success' nor 'working' (which means failure)
    :param return_value: dict
    :param message: string
    """
    if not isinstance(return_value, dict):
        error = u'Unknown answer format from kuberdock'
        msg = _format_msg(error, message, return_value)
        current_app.logger.warning(msg)
    else:
        # TODO: handle kubernetes error (APIError?) and test that
        # it will not break anything
        if return_value.get('kind') != u'Status':
            return
        status = return_value.get('status')
        if not isinstance(status, basestring):
            error = u'Unknown kubernetes status answer'
            msg = _format_msg(error, message, return_value)
            current_app.logger.warning(msg)
            return
        if status.lower() not in ('success', 'working'):
            error = u'Error in kubernetes answer'
            msg = _format_msg(error, message, return_value)
            raise_(msg)


def make_name_from_image(image):
    """
    Appends random part to image
    :param image: string -> image name
    """
    n = '-'.join(x.lower() for x in image.split('/'))
    return "%s-%s" % (n, ''.join(
        random.sample(string.ascii_lowercase + string.digits, 10)))


def merge_lists(list_1, list_2, key, replace=False):
    merged = {}
    for item in list_1 + list_2:
        item_key = item[key]
        if item_key in merged:
            if replace:
                merged[item_key].update(item)
            else:
                merged[item_key].update(
                    item.items() + merged[item_key].items()
                )
        else:
            merged[item_key] = item
    return merged.values()

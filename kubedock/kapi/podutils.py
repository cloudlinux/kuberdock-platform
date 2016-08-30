import random
import string

from flask import current_app

from ..exceptions import APIError

K8S_ANSWER_ERROR = u'Error in kubernetes answer'
K8S_UNKNOWN_ANSWER_STATUS_ERROR = u'Unknown kubernetes status answer'
KD_UNKNOWN_ANSWER_FORMAT_ERROR = u'Unknown answer format from kuberdock'


def raise_(message, code=409):
    raise APIError(message, status_code=code)


def _format_msg(error, message, return_value):
    msg = error
    if message:
        msg = u'({}) {}'.format(error, message)
    return u'{}: {}'.format(msg, unicode(return_value))


def raise_if_failure(return_value, message=None, api_error=None):
    """
    Raises error if request to k8s fails
    :param return_value: k8s answer as dictionary
    :param message: APIError message sent to user in case of an error. Defaults
                    to a message composed from k8s answer and err_msg from
                    is_failed_k8s_answer
    :type return_value: dict
    :type message: str
    """
    failed, err_msg = is_failed_k8s_answer(return_value)
    if not failed:
        return

    msg = _format_msg(err_msg, message, return_value)
    if err_msg != K8S_ANSWER_ERROR:
        current_app.logger.warning(msg)
        return

    current_app.logger.error(msg)
    if api_error:
        raise api_error
    raise_(message)


def is_failed_k8s_answer(return_value):
    """
    If return_value has 'status' field and it's not 'success' or 'working'
    return a tuple indicating that there was failure in request to k8s.
    :param return_value: k8s answer as dictionary
    :type return_value: dict
    :returns: (ERR_FLAG, ERR_MESSAGE)
    :rtype: tuple([boolean, str])
    """
    if not isinstance(return_value, dict):
        err_msg = KD_UNKNOWN_ANSWER_FORMAT_ERROR
        return (True, err_msg)
    else:
        if return_value.get('kind') != u'Status':
            return (False, None)
        status = return_value.get('status')
        if not isinstance(status, basestring):
            err_msg = K8S_UNKNOWN_ANSWER_STATUS_ERROR
            return (True, err_msg)
        if status.lower() not in ('success', 'working'):
            err_msg = K8S_ANSWER_ERROR
            return (True, err_msg)
    return (False, None)


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

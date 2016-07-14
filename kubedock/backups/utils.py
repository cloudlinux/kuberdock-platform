import urlparse


def join_url(base_url, path):
    """Joins base url and path removing extra slashes.
    Removes trailing slashes. Joins queries.
    E.g.: See unit tests.
    :param base_url: Base url.
    :param path: Path.
    :return: Joined url.
    """
    # Example of usages see in unittests
    base_url = urlparse.urlsplit(base_url, allow_fragments=False)
    path = urlparse.urlsplit(path, allow_fragments=False)
    full_path = _join_paths(base_url.path, path.path)
    full_query = _join_queries(base_url.query, path.query)
    return urlparse.urlunsplit(
        (base_url.scheme, base_url.netloc, full_path, full_query,
         base_url.fragment))


def _join_paths(*parts):
    rv = ''
    for part in parts:
        x = part.strip('/')
        if x:
            rv += '/' + x
    return rv


def _join_queries(*parts):
    non_empty_parts = (p for p in parts if p)
    return '&'.join(non_empty_parts)

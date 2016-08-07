from ..base import ClientBase


class ImagesClient(ClientBase):
    endpoint = '/images'

    def search(self, search_key, page=None, per_page=None, refresh_key=None,
               registry=None):
        params = {'searchkey': search_key}
        params.update(_filter_not_none(
            page=page, per_page=per_page, refresh_key=refresh_key,
            url=registry))

        return self.transport.get(
            self._url(),
            params=params
        )


def _filter_not_none(**kwargs):
    return {k: v for k, v in kwargs.items() if v is not None}

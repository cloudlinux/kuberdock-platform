import unittest

from ..utils import get_api_url


class TestUtilsGetApiUrl(unittest.TestCase):

    def test_expected_urls(self):
        self.assertEquals('http://localhost:8080/api/v1/pods',
                          get_api_url('pods', namespace=False))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods',
            get_api_url('pods'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods',
            get_api_url('pods', namespace='default'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/default/pods/some-pod',
            get_api_url('pods', 'some-pod'))

        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/zxc/pods/asd',
            get_api_url('pods', 'asd', namespace='zxc'))

        self.assertEquals('http://localhost:8080/api/v1/namespaces',
                          get_api_url('namespaces', namespace=False))

        self.assertEquals('http://localhost:8080/api/v1/namespaces/asd',
                          get_api_url('namespaces', 'asd', namespace=False))

        self.assertEquals('ws://localhost:8080/api/v1/endpoints?watch=true',
                          get_api_url('endpoints', namespace=False, watch=True))

        self.assertEquals(
            'ws://localhost:8080/api/v1/namespaces/test/endpoints?watch=true',
            get_api_url('endpoints', namespace='test', watch=True))

        self.assertEquals(
            'ws://localhost:8080/api/v1/namespaces/n/endpoints/t1?watch=true',
            get_api_url('endpoints', 't1', namespace='n', watch=True))

        # Special pod name
        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094/pods/unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
            get_api_url(
                'pods', 'unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
                namespace='user-unnamed-1-82cf712fd0bea4ac37ab9e12a2ee3094'))

        # Special ns name
        self.assertEquals(
            'http://localhost:8080/api/v1/namespaces/user-unnamed-1-v1cf712fd0bea4ac37ab9e12a2ee3094/pods/unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
            get_api_url(
                'pods', 'unnamed-1aj3q02ep9bv1rtu6z7wf-c4h6t',
                namespace='user-unnamed-1-v1cf712fd0bea4ac37ab9e12a2ee3094'))


if __name__ == '__main__':
    unittest.main()

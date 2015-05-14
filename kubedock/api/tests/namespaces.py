import unittest

from ..namespaces import Namespaces


class NamespacesTestCase(unittest.TestCase):

    CREATED_NAMESPACES = []

    def setUp(self):
        ## 1 init app
        ## 2 authenticate
        pass

    def tearDown(self):
        ## delete created namespaces
        pass

    def Xtest_get_namespaces(self):
        res = Namespaces.all()
        print res

    def Xtest_create_namespace(self):
        username = 'user1'
        podname = 'pod1'
        config = Namespaces.make_config(username, podname)
        res = Namespaces.create(config)
        self.CREATED_NAMESPACES.append(config.get('id'))
        print res

    def Xtest_delete_namespace(self):
        for ns_name in self.CREATED_NAMESPACES:
            res = Namespaces.delete(ns_name)
            print ns_name, res

    def test_create_get_delete(self):
        # create namespace
        username = 'user1'
        podname = 'pod1'
        config = Namespaces.make_config(username, podname)
        res = Namespaces.create(config)
        print res
        # get namespaces
        res = Namespaces.all()
        print res
        # delete created namespace
        res = Namespaces.delete(config.get('id'))
        print res

if __name__ == '__main__':
    unittest.main()

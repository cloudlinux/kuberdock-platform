# -*- coding: UTF-8 -*-
import xml.etree.ElementTree as ET
import new

from exceptions import OpenNebulaException


class WrongNameError(OpenNebulaException):
    pass


class WrongIdError(OpenNebulaException):
    pass

def extractString(xml_or_string):
    if isinstance(xml_or_string, str):
        return xml_or_string
    else:
        return xml_or_string.text or ''

class Template(object):
    def __init__(self, xml_element, multiple=[]):
        self.xml = ET.tostring(xml_element)
        self.xml_element = xml_element
        self.multiple = multiple
        self.parse()

    def parse(self):
        for element in self.xml_element:
            tag = element.tag
            if tag in self.multiple:
                self.parse_multiple(tag, element)
            else:
                setattr(self, tag.lower(), element.text)

    def parse_multiple(self, tag, element):
        attr = tag.lower() + 's'
        attr_list = getattr(self, attr, [])

        class_obj = new.classobj(tag.capitalize(), (Template,), {})

        attr_list.append(class_obj(element))
        setattr(self, attr, attr_list)


class XMLElement(object):
    XML_TYPES = {}

    def __init__(self, xml=None):
        if not (xml is None or ET.iselement(xml)):
            xml = ET.fromstring(xml)
        self.xml = xml

    def _initialize_xml(self, xml, root_element):
        self.xml = ET.fromstring(xml)
        if self.xml.tag != root_element.upper():
            self.xml = None
        self._convert_types()

    def __getitem__(self, key):
        value = self.xml.find(key.upper())
        if value is not None:
            if value.text:
                return value.text
            else:
                return value
        else:
            raise IndexError("Key {0} not found!".format(key))

    def __getattr__(self, name):
        try:
            return self[name]
        except (IndexError, TypeError):
            raise AttributeError(name)

    def _convert_types(self):
        for name, fun in self.XML_TYPES.items():
            if isinstance(fun, list):
                tag, cls = fun[0], fun[1]
                xml = self.xml.find(tag)
                setattr(self, name, cls(xml, *fun[2:]))
            else:
                setattr(self, name, fun(self[name]))


class Pool(list, XMLElement):
    def __init__(self, pool, element, client):
        super(Pool, self).__init__()

        self.pool_name = pool
        self.element_name = element
        self.client = client

    def info(self, filter=-3, range_start=-1, range_end=-1, *args):
        '''
        Retrives/Refreshes resource pool information

        ``filter``
            Filter flag. By defaults retrives only connected user reources.

        ``range_start``
            Range start ID. -1 for all

        ``range_end``
            Range end ID. -1 for all
        '''
        self[:] = []
        data = self.client.call(self.METHODS['info'], filter,
                                        range_start, range_end, *args)
        self._initialize_xml(data, self.pool_name)
        for element in self.xml.findall(self.element_name):
            self.append(self._factory(element))

    def _factory(self):
        pass

    def get_by_id(self, id):
        for i in self:
            if i.id == id:
                return i
        raise WrongIdError()

    def get_by_name(self, name):
        for i in self:
            if i.name == name:
                return i
        raise WrongNameError()


class PoolElement(XMLElement):
    def __init__(self, xml, client):
        super(PoolElement, self).__init__(xml)
        self.client = client

    @classmethod
    def new_with_id(cls, client, element_id):
        '''
        Retrives object which id equals ```id```.

        Arguments

        ```client```
           oca.Client object.
        ```element_id``
           object id.
        '''
        element = cls.ELEMENT_NAME
        xml = '<{0}><ID>{1}</ID></{0}>'.format(element, element_id)
        obj = cls(xml, client)
        obj.id = int(obj.id)
        return obj

    def info(self, *args):
        data = self.client.call(self.METHODS['info'], self.id)
        self._initialize_xml(data, self.ELEMENT_NAME)

    def delete(self):
        '''
        Deletes current object from the pool
        '''
        self.client.call(self.METHODS['delete'], self.id)


#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from xml.dom import minidom

import six

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.interfaces import IElementHandler

from nti.base._compat import text_

from nti.contentfragments.interfaces import IPlainTextContentFragment
from nti.contentfragments.interfaces import ISanitizedHTMLContentFragment

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


def resolve_modelcontent_body(data):
    result = []
    data = [data] if isinstance(data, six.string_types) else data
    for item in data or ():
        if isinstance(item, six.string_types):
            item = ISanitizedHTMLContentFragment(item)
            result.append(item)
    result = u'\n'.join(x for x in result if x)
    return result


@interface.implementer(IElementHandler)
class AbstractElementHandler(object):

    def __init__(self, context):
        self.context = context

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @Lazy
    def doc_id(self):
        # pylint: disable=no-member
        return self.intids.queryId(self.context)
    identifier = doc_id

    @Lazy
    def course(self):
        return find_interface(self.context, ICourseInstance, strict=False)

    def addTextNode(self, xmldoc, parent, name, value):
        node = xmldoc.createElement(name)
        node.appendChild(xmldoc.createTextNode(text_(value)))
        parent.appendChild(node)

    @classmethod
    def to_plain_text(cls, content):
        return component.getAdapter(content,
                                    IPlainTextContentFragment,
                                    name='text')

    @classmethod
    def safe_xml_text(cls, content):
        writer = six.StringIO()
        element = minidom.Text()
        element.data = content
        element.writexml(writer)
        writer.seek(0)
        return writer.read()


@component.adapter(interface.Interface)
class NullElementHandler(AbstractElementHandler):

    def iter_items(self):
        return ()

    def iter_resources(self):
        return ()

    def write_to(self, unused_archive=None):
        pass

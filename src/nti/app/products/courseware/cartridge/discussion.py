#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from xml.dom import minidom

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler
from nti.app.products.courseware.cartridge.mixins import resolve_modelcontent_body

from nti.contenttypes.presentation.interfaces import INTIDiscussionRef

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.ntiids.ntiids import find_object_with_ntiid

logger = __import__('logging').getLogger(__name__)


@component.adapter(ITopic)
class TopicHandler(AbstractElementHandler):

    def toXML(self):
        pass
    
    def toArchiveXML(self):
        topic = self.context
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "topic", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "xmlns",
                                "http://www.imsglobal.org/xsd/imsccv1p1/imsdt_v1p1")
        doc_root.setAttributeNS(None, "xmlns:xsi",
                                "http://www.w3.org/2001/XMLSchema-instance")
        doc_root.setAttributeNS(None, "xsi:schemaLocation",
                                "http://www.imsglobal.org/xsd/imsccv1p1/imsdt_v1p1 "
                                "http://www.imsglobal.org/profile/cc/ccv1p1/ccv1p1_imsdt_v1p1.xsd")

        # add title
        node = xmldoc.createElement("title")
        node.appendChild(xmldoc.createTextNode(self.to_plain_text(topic.title or '')))
        doc_root.appendChild(node)
        # add content
        node = xmldoc.createElement("text")
        node.setAttributeNS(None, "texttype", "text/html")
        content = resolve_modelcontent_body(topic.body)
        node.appendChild(xmldoc.createTextNode(content))
        doc_root.appendChild(node)
        return doc_root

    def write(self):
        """
        Write the necesary files to the archive
        """


@component.adapter(INTIDiscussionRef)
class DiscussionRefHandler(AbstractElementHandler):

    @Lazy
    def topic(self):
        return find_object_with_ntiid(self.context.target)

    def toXML(self):
        """
        returns the minidom implementation of the manifest element
        """

    def write(self):
        """
        Write the necesary files to the archive
        """

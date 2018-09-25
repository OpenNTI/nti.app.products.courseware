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

from zope.interface.common.idatetime import IDateTime

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler
from nti.app.products.courseware.cartridge.mixins import resolve_modelcontent_body

from nti.contenttypes.presentation.interfaces import INTIDiscussionRef

from nti.dataserver.contenttypes.forums.interfaces import IForum
from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.externalization.externalizer import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ITopic)
class TopicHandler(AbstractElementHandler):

    def iter_nodes(self):
        return ()

    # cartridge

    def topic(self):
        """
        Return a minidom for the topic file
        """
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
        self.addTextNode(xmldoc, doc_root, "title",
                         self.to_plain_text(topic.title or ''))
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

    def resource_topic_node(self):
        topic = self.topic
        # pylint: disable=no-member
        doc_id = self.intids.queryId(topic)
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "resource", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "type", "imsdt_xmlv1p1")
        doc_root.setAttributeNS(None, "identifier", "%s" % doc_id)
        # file
        node = xmldoc.createElement("file")
        node.setAttributeNS(None, "href", "%s.xml" % doc_id)
        doc_root.appendChild(node)
        # dependency
        node = xmldoc.createElement("dependency")
        node.setAttributeNS(None, "identifierref", "%s" % self.doc_id)
        doc_root.appendChild(node)
        return doc_root

    def resource_reference_node(self):
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "resource", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "identifier", "%s" % self.doc_id)
        doc_root.setAttributeNS(None, "href", "%s.xml" % self.doc_id)
        doc_root.setAttributeNS(None, "type",
                                "associatedcontent/imscc_xmlv1p1/learning-application-resource")
        node = xmldoc.createElement("file")
        node.setAttributeNS(None, "href", "%s.xml" % self.doc_id)
        doc_root.appendChild(node)
        return doc_root

    def iter_resources(self):
        return (self.resource_topic_node(),
                self.resource_reference_node())

    # cartridge

    @Lazy
    def createdTime(self):
        return getattr(self.topic, 'createdTime', 0)

    @Lazy
    def position(self):
        forum = find_interface(self.topic, IForum, strict=False)
        if forum is not None:
            count = 0
            for t in forum.values():
                if t == self.topic:
                    return count
                count += 1
        return 0

    def topicMeta(self):
        """
        Return a minidom for the topicMeta file
        """
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "topicMeta", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "identifier", "%s" % self.doc_id)
        doc_root.setAttributeNS(None, "xmlns",
                                "http://canvas.instructure.com/xsd/cccv1p0")
        doc_root.setAttributeNS(None, "xmlns:xsi",
                                "http://www.w3.org/2001/XMLSchema-instance")
        doc_root.setAttributeNS(None, "xsi:schemaLocation",
                                "http://canvas.instructure.com/xsd/cccv1p0 "
                                "http://canvas.instructure.com/xsd/cccv1p0.xsd")
        # add fields
        # pylint: disable=no-member
        self.addTextNode(xmldoc, doc_root, "title",
                         self.to_plain_text(self.context.title or ''))
        self.addTextNode(xmldoc, doc_root, "topic_id",
                         self.intids.queryId(self.topic))

        self.addTextNode(xmldoc, doc_root, "type", 'announcement')
        self.addTextNode(xmldoc, doc_root, "allow_rating", 'false')
        self.addTextNode(xmldoc, doc_root, "module_locked", 'active')
        self.addTextNode(xmldoc, doc_root, "sort_by_rating", 'false')
        self.addTextNode(xmldoc, doc_root, "workflow_state", 'active')
        self.addTextNode(xmldoc, doc_root, "has_group_category", 'false')
        self.addTextNode(xmldoc, doc_root, "only_graders_can_rate", 'false')
        self.addTextNode(xmldoc, doc_root, "discussion_type", 'side_comment')

        createdTime = IDateTime(self.createdTime)
        createdTime = to_external_object(createdTime)
        self.addTextNode(xmldoc, doc_root, "posted_at", createdTime)
        self.addTextNode(xmldoc, doc_root, "delayed_post_at", createdTime)

        self.addTextNode(xmldoc, doc_root, "position", self.position)
        return doc_root

    def write(self):
        """
        Write the necesary files to the archive
        """

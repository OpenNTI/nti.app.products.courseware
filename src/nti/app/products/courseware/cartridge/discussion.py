#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from xml.dom import minidom

from zope import component

from zope.cachedescriptors.property import Lazy

from zope.interface.common.idatetime import IDateTime

from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler
from nti.app.products.courseware.cartridge.mixins import resolve_modelcontent_body

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.contenttypes.presentation.interfaces import INTIDiscussionRef

from nti.dataserver.contenttypes.forums.interfaces import IForum
from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.externalization.externalizer import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ITopic)
class TopicHandler(AbstractElementHandler):

    def iter_items(self):
        return ()

    def iter_resources(self):
        return ()

    # cartridge

    def topic(self):
        """
        Return a minidom for the topic file
        """
        topic = self.context
        renderer = get_renderer("discussion_topic", ".pt")
        context = {
            'title': self.to_plain_text(topic.title or ''),
        }
        # write content
        content = resolve_modelcontent_body(topic.headline.body)
        context['text'] = self.safe_xml_text(content)
        return execute(renderer, {"context":context})

    def write_to(self, archive):
        content = self.topic()
        name = "%s.xml" % self.identifier
        with open(os.path.join(archive, name), "w") as fp:
            fp.write(content)


@component.adapter(INTIDiscussionRef)
class DiscussionRefHandler(AbstractElementHandler):

    def iter_items(self):
        return ()

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
        Return a the content for the topicMeta file
        """
        # pylint: disable=no-member
        createdTime = IDateTime(self.createdTime)
        createdTime = to_external_object(createdTime)
        renderer = get_renderer("discussion_topic_meta", ".pt")
        context = {
            'identifier': self.doc_id,
            'title': self.to_plain_text(self.context.title or ''),
            'topic_id': self.intids.queryId(self.topic),
            'type': 'announcement',
            "allow_rating": 'false',
            "module_locked": 'active',
            "sort_by_rating": 'false',
            "workflow_state": 'active',
            "has_group_category": 'false',
            "only_graders_can_rate": 'false',
            "discussion_type": 'side_comment',
            'posted_at': createdTime,
            "delayed_post_at": createdTime,
            "position": self.position
        }
        return execute(renderer, {"context":context})

    def write_to(self, archive):
        content = self.topicMeta()
        name = "%s.xml" % self.identifier
        with open(os.path.join(archive, name), "w") as fp:
            fp.write(content)

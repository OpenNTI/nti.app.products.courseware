#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

import six

from bs4 import BeautifulSoup

from collections import defaultdict

from xml.dom import minidom

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.interface.common.idatetime import IDateTime

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.authentication import get_remote_user

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import IIMSDiscussionTopic, IIMSResource, IIMSAssociatedContent

from nti.app.products.courseware.cartridge.mixins import NullElementHandler
from nti.app.products.courseware.cartridge.mixins import AbstractElementHandler
from nti.app.products.courseware.cartridge.mixins import resolve_modelcontent_body

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.contentfile.interfaces import IContentBlobFile

from nti.contenttypes.courses.discussions.utils import resolve_discussion_course_bundle

from nti.contenttypes.presentation.interfaces import INTIDiscussionRef

from nti.coremetadata.interfaces import ICanvas
from nti.coremetadata.interfaces import IEmbeddedVideo

from nti.dataserver.contenttypes.forums.interfaces import IForum
from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.externalization.externalization.externalizer import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@component.adapter(ITopic)
class TopicHandler(NullElementHandler):

    def topic(self):
        """
        Return the content for the topic file
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

    def write_to(self, archive):  # pylint: disable=signature-differs
        content = self.topic()
        name = "%s.xml" % self.identifier
        with open(os.path.join(archive, name), "w") as fp:
            fp.write(content.encode('utf-8'))


@component.adapter(IContentBlobFile)
@interface.implementer(IIMSAssociatedContent)
class IMSAssociatedContentFileBlob(object):

    createFieldProperties(IIMSAssociatedContent)

    def __init__(self, context):
        self.context = context

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @Lazy
    def filename(self):
        return self.context.filename

    def export(self, archive):
        target_path = os.path.join(archive, self.filename)
        dirname = os.path.dirname(target_path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        with open(target_path, 'w') as fd:
            fd.write(self.context.data)


@component.adapter(INTIDiscussionRef)
@interface.implementer(IIMSDiscussionTopic)
class IMSDiscussionTopic(object):

    createFieldProperties(IIMSDiscussionTopic)

    def __init__(self, context):
        self.context = context
        self.dependencies = defaultdict(list)
        if self.topic is None:
            raise TypeError  # This handles junk discussions

    # TODO we are losing <br> tags for some reason
    def _to_html(self, content):
        content_html = BeautifulSoup('', 'html5lib')
        for part in content:
            if ICanvas.providedBy(part):
                # We aren't tackling exporting canvas's at this time
                continue
            elif IEmbeddedVideo.providedBy(part):
                # Sometimes this has `//` prepended for an unknown reason
                embed = part.embedURL.lstrip('/')
                # And it's missing a resolve sometimes
                if not embed.startswith('https://') or embed.startswith('http://'):
                    # It may be worth forcing https as canvas blocks iframed http addresses
                    embed = 'https://' + embed
                iframe = content_html.new_tag('iframe')
                iframe.attrs['src'] = embed
                iframe.attrs['width'] = '640'
                iframe.attrs['height'] = '385'
                iframe.attrs['frameborder'] = '0'
                content_html.body.append(iframe)
            elif IContentBlobFile.providedBy(part):
                # Attachment
                dependency = IIMSResource(part)
                self.dependencies['files'].append(dependency)
                anchor = content_html.new_tag('a')
                anchor.attrs['href'] = 'files/%s' % dependency.filename
                anchor.string = dependency.filename
                content_html.body.append(anchor)
            elif isinstance(part, six.string_types):
                # Just html, lets append it in to the tree
                for element in BeautifulSoup(part, features='lxml').body:  # passing the feature mutes BS warning
                    content_html.body.append(element)
            else:
                # Don't know / unsupported. Log and move on
                continue
        return content_html.prettify()

    @Lazy
    def topic(self):
        # Hopefully we can just grab this straight from the target
        topic = find_object_with_ntiid(self.context.target)
        # TODO hadnle unresolvable
        if topic is None:
            # Ok, we have a course discussion. We need to resolve from the package
            user = get_remote_user()
            course_discussion, topic = resolve_discussion_course_bundle(user, self.context) or (None, None)
        # if topic is None:
        #     # If we still don't have it we need to error
        #     raise CommonCartridgeExportException(u'Unable to locate topic for discussion: %s' % self.context.title)
        return topic

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @property
    def dirname(self):
        if self.dependencies:
            return unicode(self.identifier)
        return None

    @Lazy
    def filename(self):
        return '%s.xml' % unicode(self.identifier)

    def export(self, archive):
        # TODO this properly imports; however, we could further extend canvas compatibility by adding a topic meta file
        renderer = get_renderer("discussion_topic", ".pt")
        context = {
            'title': getattr(self.topic, 'title', 'Untitled Discussion')
        }
        content = self._to_html(self.topic.headline.body)
        # TODO do we need to sanitize?
        context['text'] = content
        body = execute(renderer, {"context": context})
        if self.dirname:
            target_path = os.path.join(archive, self.dirname, self.filename)
            dirname = os.path.dirname(target_path)
            if not os.path.exists(dirname):
                os.makedirs(dirname)
        else:
            target_path = os.path.join(archive, self.filename)
        with open(target_path, "w") as fd:
            fd.write(body.encode('utf-8'))


@component.adapter(INTIDiscussionRef)
class DiscussionRefHandler(AbstractElementHandler):

    @Lazy
    def topic(self):
        return find_object_with_ntiid(self.context.target)

    @Lazy
    def topic_id(self):
        # pylint: disable=no-member
        return self.intids.queryId(self.topic)

    # manifest items

    def iter_items(self):
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "item", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "identifier", "%s" % self.identifier)
        doc_root.setAttributeNS(None, "identifierref", "%s" % self.topic_id)
        self.addTextNode(xmldoc, doc_root, "title", self.context.title or '')
        return (doc_root,)

    # manifest resources

    def resource_topic_node(self):
        DOMimpl = minidom.getDOMImplementation()
        xmldoc = DOMimpl.createDocument(None, "resource", None)
        doc_root = xmldoc.documentElement
        doc_root.setAttributeNS(None, "type", "imsdt_xmlv1p1")
        doc_root.setAttributeNS(None, "identifier", "%s" % self.topic_id)
        # file
        node = xmldoc.createElement("file")
        node.setAttributeNS(None, "href", "%s.xml" % self.topic_id)
        doc_root.appendChild(node)
        # dependency
        node = xmldoc.createElement("dependency")
        node.setAttributeNS(None, "identifierref", "%s" % self.identifier)
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
        Return the content for the topicMeta file
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
        return execute(renderer, {"context": context})

    def write_to(self, archive):
        content = self.topicMeta()
        name = "%s.xml" % self.identifier
        with open(os.path.join(archive, name), "w") as fp:
            fp.write(content)

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
from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent
from nti.common import random

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
                self.dependencies['dependencies'].append(dependency)
                anchor = content_html.new_tag('a')
                anchor.attrs['href'] = '$IMS-CC-FILEBASE$/dependencies/%s' % dependency.filename
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
        if topic is None:  # TODO
            # If we still don't have it we need to error
            raise KeyError
            #raise CommonCartridgeExportException(u'Unable to locate topic for discussion: %s' % self.context.title)
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

    @Lazy
    def title(self):
        return getattr(self.topic, 'title', 'Untitled Discussion')

    def export(self, archive):
        renderer = get_renderer("discussion_topic", ".pt")
        context = {
            'title': self.title
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


# TODO could live in app products ou
@interface.implementer(IIMSAssociatedContent)
class CanvasTopicMeta(AbstractIMSWebContent):

    createFieldProperties(IIMSAssociatedContent)

    def __init__(self, cc_discussion):
        self.cc_discussion = cc_discussion
        # TODO I don't think this identifier is useful in our context
        self.assignment_identifier = random.generate_random_string(10)

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @Lazy
    def discussion_identifier(self):
        return self.cc_discussion.identifier

    @Lazy
    def filename(self):
        return u'topic_meta.xml'

    def export(self, archive):
        path_to = os.path.join(archive, self.filename)
        renderer = get_renderer('templates/canvas/topic_meta', '.pt')
        context = {'identifier': self.identifier,
                   'discussion_identifier': self.discussion_identifier,
                   'title': self.cc_discussion.title,
                   'assignment_identifier': self.assignment_identifier}
        xml = execute(renderer, {'context': context})
        self.write_resource(path_to, xml)
        return True

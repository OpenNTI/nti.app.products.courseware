#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

import six
from bs4 import BeautifulSoup
from premailer import Premailer

from pyramid.threadlocal import get_current_request

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy
from zope.interface.interfaces import ComponentLookupError

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.assessment.common.policy import get_policy_excluded
from nti.app.products.courseware.cartridge.discussion import CanvasTopicMeta
from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import IIMSAssignment, IIMSResource, ICommonCartridgeAssessment

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent
from nti.app.products.courseware.cartridge.web_content import IMSWebContent

from nti.app.products.courseware.qti.interfaces import IQTIAssessment

from nti.app.products.courseware.qti.utils import update_external_resources, mathjax_parser

from nti.assessment import IQuestionSet

from nti.assessment.interfaces import IQAssignment, IQDiscussionAssignment, IQEditableEvaluation
from nti.assessment.interfaces import IQNonGradableFilePart
from nti.contentlibrary.interfaces import IPersistentFilesystemContentUnit
from nti.contenttypes.courses.discussions.utils import get_topic_key

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.contenttypes.forums.interfaces import ICommunityHeadlineTopic

from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def _is_only_file_part_questions(questions):
    part = questions[0].parts[0]
    return len(questions) == 1 and IQNonGradableFilePart.providedBy(part)


def _is_only_file_part(assessment):
    if len(assessment.parts) != 1:
        return None
    question_set = assessment.parts[0].question_set
    return _is_only_file_part_questions(question_set.questions)


@interface.implementer(ICommonCartridgeAssessment)
def adapt_to_common_cartridge_assessment(assessment):
    course = get_current_request().context
    if not ICourseInstance.providedBy(course):
        raise CommonCartridgeExportException(u'Request context does not provide a course instance')
    if get_policy_excluded(assessment, course):
        raise CommonCartridgeExportException(u'Section course assessment %s skipped' % assessment.title)
    if IQAssignment.providedBy(assessment) and _is_only_file_part(assessment):
        return CanvasAssignment(assessment)
    elif IQuestionSet.providedBy(assessment) and _is_only_file_part_questions(assessment.questions):
        return CanvasAssignment(assessment)
    elif IQDiscussionAssignment.providedBy(assessment):
        # These are the same as a regular discussion we just patch in
        # some metadata to identify it as an assignment
        # TODO This should be generalized to be site specific instead of hard patching it in
        discussion = find_object_with_ntiid(assessment.discussion_ntiid)
        if discussion is None:
            raise CommonCartridgeExportException(u'Unable to resolve a discussion for discussion assignment %s' % assessment)
        topic_key = get_topic_key(discussion)
        topic = None
        for val in course.Discussions.values():
            if topic_key in val:
                topic = val[topic_key]
                break
        if topic is None:
            raise CommonCartridgeExportException(u'Unable to resolve a topic for discussion %s' % discussion)
        resource = IIMSResource(discussion)
        assessment_content, dependencies = update_external_resources(assessment.content)
        resource.extra_content = assessment_content
        resource.dependencies['dependencies'].extend(dependencies)
        resource.topic = topic  # TODO messy messy messy
        resource.dependencies[resource.identifier].append(CanvasTopicMeta(resource))
        return resource
    else:
        qti = component.queryMultiAdapter((assessment, course), IQTIAssessment)
        qti.type = u'imsqti_xmlv1p2/imscc_xmlv1p1/assessment'  # Different in common cartridge
        return qti


@interface.implementer(IIMSAssignment)
class CanvasAssignment(AbstractIMSWebContent):

    createFieldProperties(IIMSAssignment)

    def handle_dependencies(self, deps):
        """
        Convert a list of hrefs into IMSWebContent to maintain a standard format
        """
        for dep in deps:
            # Hard refs
            if isinstance(dep, six.text_type):
                web_content = IMSWebContent(self.context, dep)
                self.dependencies['dependencies'].append(web_content)
            # MathJax / other  # TODO this could be better but we are running out of time
            else:
                self.dependencies['mathjax'].append(dep)

    def __init__(self, context):
        super(CanvasAssignment, self).__init__(context)
        if getattr(context, 'content', False) == False:
            raise ComponentLookupError
        if not self.is_content_backed:
            content = context.content + '\n' + self.question.content
        else:
            content = self._parse_content()
        # Ok, now that everything is clean, parse what will be the description for images and other linked resources
        # Check for resource refs and add to dependencies
        new_content, dependencies = update_external_resources(content, 'dependencies')
        self.handle_dependencies(dependencies)
        self.content = mathjax_parser(new_content)

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @Lazy
    def assignment_identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self.context)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @Lazy
    def title(self):
        return self.context.title

    @Lazy
    def context_parent(self):
        return self.context.__parent__

    @Lazy
    def is_content_backed(self):
        return not IQEditableEvaluation.providedBy(self.context_parent) \
               and IPersistentFilesystemContentUnit.providedBy(self.context_parent)

    @Lazy
    def content_file(self):
        if self.is_content_backed:
            return self.context_parent.key

    def content_soup(self, styled=False):
        if self.is_content_backed:
            text = self.content_file.read_contents_as_text()
            if styled:
                base_url = self.content_file.absolute_path
                # This inlines external style sheets
                premailer = Premailer(text,
                                      base_url=base_url,
                                      disable_link_rewrites=True)
                text = premailer.transform()
            text = mathjax_parser(text)
            return BeautifulSoup(text, features='html5lib')

    def _is_internal_resource(self, href):
        return not bool(urllib_parse.urlparse(href).scheme)

    def _parse_content(self):
        """
        Attempt to take a content backed assignment page contents and strip it down for external usage.
        Specifically, object references. We will also attempt to
        build dependencies on any internal resources
        """
        page_contents = self.content_soup().find_all('div', {'class': 'page-contents'})
        new_content = BeautifulSoup(features='html.parser')
        to_be_extracted = []  # Because we recurse the structure we need to delay extraction until we are finished
        for pg in page_contents:  # Most likely len(page_contents) == 1
            for tag in pg.recursiveChildGenerator():
                # Extract marker anchor tags
                if hasattr(tag, 'name') and \
                        tag.name == 'a' and \
                        hasattr(tag, 'attrs') and \
                        'name' in tag.attrs and \
                        len(tag.attrs) == 1:
                    to_be_extracted.append(tag)
            new_content.append(pg)

        for tag in to_be_extracted:
            tag.extract()
        to_be_extracted = []

        # Strip objects and handle interlaced text
        question_objects = new_content.find_all('object',
                                                {'type': ('application/vnd.nextthought.naquestion',
                                                          'application/vnd.nextthought.naquestionfillintheblankwordbank')})
        for question_object in question_objects:
            question_object.extract()

        for tag in to_be_extracted:
            tag.extract()
        return new_content.encode('UTF-8')

    @Lazy
    def question(self):
        if IQuestionSet.providedBy(self.context):
            return self.context.questions[0]
        else:
            return self.context.parts[0].question_set.questions[0]

    @Lazy
    def content(self):
        soup = BeautifulSoup(self.context.content, features='html.parser')
        question_soup = BeautifulSoup(self.question.content, features='html.parser')
        soup.append(question_soup)
        content, dependencies = update_external_resources(soup.decode())
        self.dependencies['dependencies'].extend([IMSWebContent(self.context, dep) for dep in dependencies])
        return content

    @Lazy
    def grading_type(self):
        # Question sets are ungraded assignments
        if IQAssignment.providedBy(self.context):
            return u'points'
        else:
            return u'not_graded'

    @Lazy
    def filename(self):
        return self.identifier + '.xml'

    def export(self, dirname):
        content = '<![CDATA[%s]]>' % self.content
        context = {'identifier': self.identifier,
                   'title': self.title,
                   'content': content,
                   'assignment_identifier': self.assignment_identifier,
                   'grading_type': self.grading_type}
        renderer = get_renderer('templates/canvas/assignment', '.pt')
        xml = execute(renderer, {'context': context})
        path_to = os.path.join(dirname, self.filename)
        self.write_resource(path_to, xml)
        return True

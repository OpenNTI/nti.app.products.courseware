#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from bs4 import BeautifulSoup

from collections import defaultdict

from datetime import timedelta

from pynliner import Pynliner  # TODO add this to buildout deps

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.assessment.common.evaluations import get_max_time_allowed

from nti.app.assessment.common.policy import get_policy_max_submissions
from nti.app.assessment.common.policy import get_policy_submission_priority
from nti.app.assessment.common.policy import get_submission_buffer_policy

from nti.app.assessment.common.utils import get_available_for_submission_beginning
from nti.app.assessment.common.utils import get_available_for_submission_ending

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer
from nti.app.products.courseware.cartridge.web_content import IMSWebContent

from nti.app.products.courseware.qti.interfaces import ICanvasQuizMeta
from nti.app.products.courseware.qti.interfaces import ICanvasAssignmentSettings
from nti.app.products.courseware.qti.interfaces import IQTIAssessment
from nti.app.products.courseware.qti.interfaces import IQTIItem
from nti.app.products.courseware.qti.utils import update_external_resources

from nti.assessment.interfaces import IQAssessment
from nti.assessment.interfaces import IQEditableEvaluation
from nti.assessment.interfaces import IQTimedAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.common import random

from nti.contentlibrary.interfaces import IPersistentFilesystemContentUnit

from nti.externalization import to_external_object

from nti.ntiids.ntiids import find_object_with_ntiid

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IQTIAssessment)
class QTIAssessment(object):

    def handle_dependencies(self, deps):
        """
        Convert a list of hrefs into IMSWebContent to maintain a standard format
        """
        for dep in deps:
            web_content = IMSWebContent(self.context, dep)
            self.dependencies['dependencies'].append(web_content)

    def __init__(self, context, course):
        self.context = context
        self.dependencies = defaultdict(list)
        self.items = []
        self.course = course
        if not self.is_content_backed:
            # Parse the questions
            for question in self.questions:
                for part in question.parts:
                    qti_item = IQTIItem(part)
                    qi_export = qti_item.to_xml()
                    self.items.append(qi_export)
                    self.handle_dependencies(qti_item.dependencies)
            # set the content
            self.content = context.content
        else:
            self.content = self._parse_content()

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    @Lazy
    def context_parent(self):
        return self.context.__parent__

    @Lazy
    def is_content_backed(self):
        return not IQEditableEvaluation.providedBy(self.context_parent) \
               and IPersistentFilesystemContentUnit.providedBy(self.context_parent)

    @Lazy
    def title(self):
        return self.context.title

    @Lazy
    def content_file(self):
        if self.is_content_backed:
            return self.context_parent.key

    def content_soup(self, styled=True):
        if self.is_content_backed:
            text = self.content_file.read_contents_as_text()
            if styled:
                # This inlines external style sheets
                content = Pynliner()
                content.root_url = self.content_file.absolute_path
                assert getattr(content, '_get_url', None)  # If this private method gets refactored, let us know
                # By default, this tries to retrieve via request, we will override
                content._get_url = lambda url: open(url).read().decode()
                content.from_string(text)
                text = content.run()
            return BeautifulSoup(text, features='lxml')

    def _is_internal_resource(self, href):
        return not bool(urllib_parse.urlparse(href).scheme)

    def _parse_content(self):
        """
        Attempt to take a content backed assignment page contents and strip it down for external usage.
        Specifically, object references. We will also attempt to
        build dependencies on any internal resources
        """
        page_contents = self.content_soup().find_all('div', {'class': 'page-contents'})
        new_content = BeautifulSoup()
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
                                                {'type': 'application/vnd.nextthought.naquestion'})
        for i, question_object in enumerate(question_objects):
            ntiid = question_object.attrs['data']
            question = find_object_with_ntiid(ntiid)
            assert question in self.questions  # sanity check
            for part in question.parts:
                qti_item = IQTIItem(part)
                self.items.append(qti_item.to_xml())
                self.handle_dependencies(qti_item.dependencies)
            nested_text = ''
            try:
                next_question_object = question_objects[i + 1]
                for sibling in question_object.next_siblings:
                    if sibling == next_question_object:
                        break
                    # Skip empty tags
                    if sibling.name is None and sibling.strip() == '':
                        continue
                    nested_text += ' ' + repr(sibling)
                    to_be_extracted.append(sibling)
            except IndexError:
                pass
            # Ok, there was text in between this object and the next. Create a text entry
            if nested_text != '':
                item_identifier = random.generate_random_string()  # Shouldn't need this identifier
                assignment_identifier_ref = random.generate_random_string()  # same as above
                renderer = get_renderer('templates/parts/text_entry', '.pt')
                context = {'item_identifier': item_identifier,
                           'title': 'Text',
                           'assignment_identifier_ref': assignment_identifier_ref,
                           'mattext': nested_text}
                self.items.append(execute(renderer, {'context': context}))
            question_object.extract()

        for tag in to_be_extracted:
            tag.extract()

        # Ok, now that everything is clean, parse what will be the description for images and other linked resources
        # Check for resource refs and add to dependencies
        new_content, dependencies = update_external_resources(new_content.prettify(), 'dependencies')
        self.handle_dependencies(dependencies)
        return new_content

    @Lazy
    def questions(self):
        if IQuestionSet.providedBy(self.context):
            return self.context.questions
        elif IQAssessment.providedBy(self.context):
            # Get q sets from assignment parts
            question_sets = (part.question_set for part in self.context.parts)
            # Coalesce the questions
            return [question for qs in question_sets for question in qs.questions]
        else:
            # Should never happen TODO handle
            return None

    def export(self):
        renderer = get_renderer('qti_assessment', '.pt')
        context = {'ident': self.identifier,
                   'title': self.context.title,
                   'items': self.items}
        return execute(renderer, {'context': context})


@interface.implementer(ICanvasAssignmentSettings)
class CanvasAssignmentSettings(object):

    createFieldProperties(ICanvasAssignmentSettings)

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
        return identifier

    @Lazy
    def ext(self):
        ext = to_external_object(self)
        ext.pop('Class')
        ext.pop('MimeType')
        ext.pop('identifier')
        return ext

    def __init__(self, qti_assessment):
        self.title = qti_assessment.title
        self.quiz_identifierref = qti_assessment.identifier

    def to_xml(self):
        renderer = get_renderer('assignment_settings', '.pt')
        context = {'fields': self.ext,
                   'identifier': self.identifier}
        return execute(renderer, {'context': context})


@interface.implementer(ICanvasQuizMeta)
class CanvasQuizMeta(object):

    nti_to_canvas_submission_map = {'highest_grade': 'keep_highest',
                                    'most_recent': 'keep_latest'}

    createFieldProperties(ICanvasQuizMeta)

    def __init__(self, qti_assessment, course):
        assessment = qti_assessment.context
        self.identifier = qti_assessment.identifier
        self.title = qti_assessment.title
        self.description = qti_assessment.content
        if IQTimedAssignment.providedBy(assessment):
            self.time_limit = get_max_time_allowed(assessment, course)
        self.allowed_attempts = get_policy_max_submissions(assessment, course)
        self.unlock_at = get_available_for_submission_beginning(assessment, context=course)
        self.due_at = get_available_for_submission_ending(assessment, context=course) or self.due_at
        submission_buffer = get_submission_buffer_policy(assessment, course) or 0
        self.lock_at = self.due_at + timedelta(seconds=submission_buffer) if self.due_at else self.lock_at
        submission_priority = get_policy_submission_priority(assessment, course)
        self.scoring_policy = self.nti_to_canvas_submission_map.get(submission_priority) or self.scoring_policy
        if IQAssessment.providedBy(assessment):
            self.quiz_type = u'assignment'
            self.assignment = CanvasAssignmentSettings(qti_assessment).to_xml()
        elif IQuestionSet.providedBy(assessment):
            self.quiz_type = u'practice_quiz'

    @Lazy
    def ext(self):
        ext = to_external_object(self)
        ext.pop('Class')
        ext.pop('MimeType')
        ext.pop('identifier')
        ext.pop('description')
        return ext

    def meta(self):
        renderer = get_renderer('assessment_meta', '.pt')
        context = {'fields': self.ext,
                   'quiz_id': self.identifier,
                   'description': self.description,
                   'assignment': getattr(self, 'assignment', None)}
        return execute(renderer, {'context': context})

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from bs4 import BeautifulSoup

from pyramid.threadlocal import get_current_request

from zope import component, interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException
from nti.app.products.courseware.cartridge.interfaces import IIMSAssignment
from nti.app.products.courseware.cartridge.renderer import get_renderer, execute
from nti.app.products.courseware.cartridge.web_content import IMSWebContent, AbstractIMSWebContent

from nti.app.products.courseware.qti.interfaces import IQTIAssessment

from nti.app.products.courseware.qti.utils import update_external_resources

from nti.assessment import IQuestionSet

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQNonGradableFilePart

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import IAssetRef

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


# TODO discussion assignments muddy this
def adapt_to_common_cartridge_assessment(assessment):
    course = get_current_request().context
    if not ICourseInstance.providedBy(course):
        raise CommonCartridgeExportException(u'Request context does not provide a course instance')
    if IAssetRef.providedBy(assessment):
        assessment = find_object_with_ntiid(assessment.target)
    if IQAssignment.providedBy(assessment) and _is_only_file_part(assessment):
        return CanvasAssignment(assessment)
    elif IQuestionSet.providedBy(assessment) and _is_only_file_part_questions(assessment.questions):
        return CanvasAssignment(assessment)
    else:
        qti = component.queryMultiAdapter((assessment, course), IQTIAssessment)
        qti.type = u'imsqti_xmlv1p2/imscc_xmlv1p1/assessment'  # Different in common cartridge
        return qti


@interface.implementer(IIMSAssignment)
class CanvasAssignment(AbstractIMSWebContent):

    createFieldProperties(IIMSAssignment)

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
        content, dependencies = update_external_resources(soup.prettify())
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
        context = {'identifier': self.identifier,
                   'title': self.title,
                   'content': self.content,
                   'assignment_identifier': self.assignment_identifier,
                   'grading_type': self.grading_type}
        renderer = get_renderer('templates/canvas/assignment', '.pt')
        xml = execute(renderer, {'context': context})
        path_to = os.path.join(dirname, self.filename)
        self.write_resource(path_to, xml)
        return True

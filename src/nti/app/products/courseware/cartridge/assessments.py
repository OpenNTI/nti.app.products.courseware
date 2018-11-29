#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from pyramid.threadlocal import get_current_request
from zope import component

from nti.app.products.courseware.qti.interfaces import IQTIAssessment
from nti.assessment import IQuestionSet
from nti.assessment.interfaces import IQNonGradableFilePart, IQAssignment

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


def _is_only_file_part_question_set(question_set):
    if IQuestionSet.providedBy(question_set):
        part = question_set.parts[0]
        if IQNonGradableFilePart.providedBy(part):
            return part
        return None


def _is_only_file_part(assessment):
    if len(assessment.parts) != 1:
        return None
    question_set = assessment.parts[0]
    return _is_only_file_part_question_set(question_set)


def adapt_to_common_cartridge_assessment(assessment):
    course = get_current_request().context
    if IQAssignment.providedBy(assessment) and _is_only_file_part(assessment):
        part = _is_only_file_part(assessment)
        return None
        #return CanvasAssignment(part)
    elif IQuestionSet.providedBy(assessment) and _is_only_file_part_question_set(assessment):
        part = _is_only_file_part_question_set(assessment)
        return None
        #return CanvasAssignment(part)
    else:
        return component.queryMultiAdapter((assessment, course), IQTIAssessment)


# TODO implement. Should probably live in nti.app.products.ou
class CanvasAssignment(object):
    pass

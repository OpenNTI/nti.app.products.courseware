#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: model.py 123306 2017-10-19 03:47:14Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.credit import CourseAwardedCredit

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollments

from nti.contenttypes.credit.interfaces import ICreditTranscript

from nti.coremetadata.interfaces import IUser

from nti.dataserver.interfaces import IEntityContainer

logger = __import__('logging').getLogger(__name__)


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ICreditTranscript)
class UserCourseCreditTranscript(object):

    def __init__(self, user, course):
        self.user = user
        self.course = course

    def _build_awarded_credit(self, awardable_credit, completed_item, entry):
        return CourseAwardedCredit(title=entry.title,
                                   credit_definition=awardable_credit.credit_definition,
                                   amount=awardable_credit.amount,
                                   awarded_date=completed_item.CompletedDate)

    def _get_course_completed_item(self):
        progress = component.queryMultiAdapter((self.user, self.course),
                                               IProgress)
        if progress is not None:
            return progress.CompletedItem

    def _get_awardable_credits(self, entry):
        """
        If the course is completable, return the awardable credits applicable
        to our user.
        """
        completion_policy = ICompletionContextCompletionPolicy(self.course,
                                                               None)
        if completion_policy is not None:
            result = []
            awardable_credits = entry.awardable_credits or ()
            for awardable_credit in awardable_credits:
                if awardable_credit.scope:
                    try:
                        scope = self.course.SharingScopes[awardable_credit.scope]
                    except KeyError:
                        scope = None
                    if      scope is not None \
                        and self.user in IEntityContainer(scope):
                        result.append(awardable_credit)
                else:
                    result.append(awardable_credit)
            return result

    def iter_awarded_credits(self):
        """
        Returns an iterator over the :class:`ICourseAwardedCredit` objects for
        this user and course.
        """
        result = []
        entry = ICourseCatalogEntry(self.course, None)
        awardable_credits = self._get_awardable_credits(entry)
        # Must have credits to grant
        if awardable_credits:
            # Course must be completed by user
            completed_item = self._get_course_completed_item()
            if completed_item:
                for awardable_credit in awardable_credits or ():
                    awarded_credit = self._build_awarded_credit(awardable_credit,
                                                                completed_item,
                                                                entry)
                    result.append(awarded_credit)
        return result


@component.adapter(IUser)
@interface.implementer(ICreditTranscript)
class AllCourseCreditTranscript(object):

    def __init__(self, user):
        self.user = user

    def iter_awarded_credits(self):
        """
        Returns an iterator over the :class:`ICourseAwardedCredit` objects for
        this user.
        """
        result = []
        enrollments = get_enrollments(self.user)
        for record in enrollments or ():
            course = ICourseInstance(record, None)
            course_transcript = component.getMultiAdapter((self.user, course),
                                                          ICreditTranscript)
            result.extend(course_transcript.iter_awarded_credits())
        return result


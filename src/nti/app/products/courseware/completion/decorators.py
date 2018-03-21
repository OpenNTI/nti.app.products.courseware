#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from zope import component
from zope import interface

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.users import User

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _CourseProgressDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates progress information on a course
    """

    def course(self, context):
        return context.CourseInstance

    def user(self, context):
        return User.get_user(context.Username)

    def _predicate(self, context, unused_result):
        return ICompletionContextCompletionPolicy(self.course(context), None) != None        

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(Link(context, rel='Progress', elements=('Progress',)))
        if 'CourseProgress' not in result:
            progress = component.queryMultiAdapter((self.user(context), self.course(context)),
                                                   IProgress)
            result['CourseProgress'] = progress

@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseProgressStatsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates a progress stats link on the course
    """

    def _predicate(self, context, unused_result):
        return ICompletionContextCompletionPolicy(context, None) != None        

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(Link(context, rel='ProgressStats', elements=('ProgressStats',)))

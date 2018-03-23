#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.completion.views import completed_items_link

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IUser

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

    def __init__(self, context, request):
        super(_CourseProgressDecorator, self).__init__(context, request)
        self.context = context

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def user(self):
        return IUser(self.context)

    def _predicate(self, unused_context, unused_result):
        return ICompletionContextCompletionPolicy(self.course, None) != None

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(Link(context, rel='Progress', elements=('Progress',)))
        if 'CourseProgress' not in result:
            progress = component.queryMultiAdapter((self.user, self.course),
                                                   IProgress)
            result['CourseProgress'] = progress

        # Provide a link to the user's completed items
        _links.append(completed_items_link(self.course(context), self.user(context)))

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

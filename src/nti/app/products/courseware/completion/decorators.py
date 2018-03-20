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

from nti.dataserver.users import User

from nti.externalization.interfaces import IExternalMappingDecorator

@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _CourseProgressDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates progress information on a course
    """

    @property
    def course(self):
        return self.context.CourseInstance

    @property
    def user(self):
        return User.get_user(self.context.Username)

    def _predicate(self, context, unused_result):
        return ICompletionContextCompletionPolicy(self.course, None) != None        

    def _do_decorate_external(self, context, result):
        if 'CourseProgress' not in result:
            progress = component.queryMultiAdapter((self.user, self.course),
                                                   IProgress)
            result['CourseProgress'] = progress

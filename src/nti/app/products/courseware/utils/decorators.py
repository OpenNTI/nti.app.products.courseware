#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


class PreviewCourseAccessPredicateDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    A predicate useful when determining whether the remote user has access to
    course materials when the course is in preview mode. The context must be
    adaptable to an `ICourseInstance`.
    """

    def __init__(self, context, request):
        super(PreviewCourseAccessPredicateDecorator, self).__init__(context, request)
        self.context = context

    def _is_preview(self, course):
        entry = ICourseCatalogEntry(course, None)
        return entry is not None and entry.Preview

    @property
    def course(self):
        # We'll want acquisition derived courses for some objects...
        result = find_interface(self.context, ICourseInstance, strict=False)
        if result is None:
            result = ICourseInstance(self.context)
        return result

    @property
    def instructor_or_editor(self):
        result = is_course_instructor_or_editor(self.course, self.remoteUser) \
              or has_permission(ACT_CONTENT_EDIT, self.course)
        return result

    def _predicate(self, unused_context, unused_result):
        """
        The course is not in preview mode, or we are an editor,
        instructor, or content admin.
        """
        return not self._is_preview(self.course) \
            or (self._is_authenticated and self.instructor_or_editor)
PreviewCourseAccessPredicate = PreviewCourseAccessPredicateDecorator  # BWC

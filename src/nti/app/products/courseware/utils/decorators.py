#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization_acl import has_permission

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
		return ICourseInstance(self.context)

	@property
	def instructor_or_editor(self):
		result = 	is_course_instructor_or_editor(self.course, self.remoteUser) \
				 or has_permission(ACT_CONTENT_EDIT, self.course, self.remoteUser)
		return result

	def _predicate(self, context, result):
		"""
		The course is not in preview mode, or we are an editor,
		instructor, or content admin.
		"""
		return 		not self._is_preview(self.course) \
				or	(self._is_authenticated and self.instructor_or_editor)

PreviewCourseAccessPredicate = PreviewCourseAccessPredicateDecorator  # BWC

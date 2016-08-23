#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Role support for legacy courses, based on the JobTitle
in the course catalog entry.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.principalrole import CourseInstancePrincipalRoleMap

from nti.property.property import CachedProperty

@interface.implementer(IPrincipalRoleMap)
@component.adapter(ILegacyCommunityBasedCourseInstance)
class LegacyCourseInstancePrincipalRoleMap(CourseInstancePrincipalRoleMap):

	@CachedProperty
	def _mapped_principals(self):
		# Sometimes we might be hit in a site that doesn't have
		# courses registered in the catalog (e.g., decorating some
		# object in the stream of a user who can use multiple sites).
		# In that case, no one has any roles or access to data.
		# This should only happen in test environments.
		entry = ICourseCatalogEntry(self.context, None)
		if entry is None:
			return ()

		# We prefer to iterate across the Instructors
		# in the entry, as that's a list, possibly where
		# order matters
		result = []
		principals = {x.id.lower(): x for x in self.context.instructors}
		for info in entry.Instructors:
			username = info.username.lower()
			if username in principals:
				result.append((principals[username],
							   RID_TA if info.JobTitle == 'Teaching Assistant' else RID_INSTRUCTOR))
		return result

	def _principals_for_ta(self):
		result = [x[0] for x in self._mapped_principals if x[1] == RID_TA]
		return result

	def _principals_for_instructor(self):
		result = [x[0] for x in self._mapped_principals if x[1] == RID_INSTRUCTOR]
		return result

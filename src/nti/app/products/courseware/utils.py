#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

def drop_any_other_enrollments(course, user):
	course_ntiid = ICourseCatalogEntry(course).ntiid
	if ICourseSubInstance.providedBy(course):
		main_course = course.__parent__.__parent__
	else:
		main_course = course
			
	result = []
	universe = [main_course] + list(main_course.SubInstances.values())
	for instance in universe:
		instance_entry = ICourseCatalogEntry(instance)
		if course_ntiid == instance_entry.ntiid:
			continue
		enrollments = ICourseEnrollments(instance)
		enrollment = enrollments.get_enrollment_for_principal(user)
		if enrollment is not None:
			enrollment_manager = ICourseEnrollmentManager(instance)
			enrollment_manager.drop(user)
			entry = ICourseCatalogEntry(instance, None)
			logger.warn("User %s dropped from course '%s' open enrollment", user,
						getattr(entry, 'ProviderUniqueID', None))
			result.append(instance)
	return result

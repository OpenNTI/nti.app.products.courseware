#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope.security.interfaces import IPrincipal
from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from .enrollment import EnrollmentOptions
from .interfaces import IEnrollmentOptionProvider

def drop_any_other_enrollments(context, user):
	course = ICourseInstance(context)
	entry = ICourseCatalogEntry(course)
	
	course_ntiid = entry.ntiid
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

def get_enrollment_options(context):
	result = EnrollmentOptions()
	entry = ICourseCatalogEntry(context)
	for provider in component.subscribers((entry,), IEnrollmentOptionProvider):
		for option in provider.iter_options():
			result.append(option)
	return result

def is_course_instructor(course, user):
	result = False
	prin = IPrincipal(user)
	roles = IPrincipalRoleMap(course, None)
	if not roles:
		result = Allow in (roles.getSetting(RID_TA, prin.id),
						   roles.getSetting(RID_INSTRUCTOR, prin.id))
	return result
			
def is_enrolled(course, user):
	enrollments = ICourseEnrollments(course)
	record = enrollments.get_enrollment_for_principal(user)
	return record is not None

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
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from .enrollment import EnrollmentOptions
from .interfaces import IEnrollmentOptionProvider

def is_there_an_open_enrollment(course, user):
	if ICourseSubInstance.providedBy(course):
		main_course = course.__parent__.__parent__
	else:
		main_course = course

	universe = [main_course] + list(main_course.SubInstances.values())
	for instance in universe:
		enrollments = ICourseEnrollments(instance)
		record = enrollments.get_enrollment_for_principal(user)
		if record is not None and record.Scope == ES_PUBLIC:
			return True
	return False

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

def is_course_instructor(context, user):
	result = False
	prin = IPrincipal(user)
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleMap(course, None)
	if roles:
		result = Allow in (roles.getSetting(RID_TA, prin.id),
						   roles.getSetting(RID_INSTRUCTOR, prin.id))
	return result

def get_catalog_entry(ntiid, safe=True):
	try:
		catalog = component.getUtility(ICourseCatalog)
		entry = catalog.getCatalogEntry(ntiid) if ntiid else None
		return entry
	except KeyError as e:
		if not safe:
			raise e
	return None

def get_enrollment_record(context, user):
	course = ICourseInstance(context, None)
	enrollments = ICourseEnrollments(course, None)
	record = enrollments.get_enrollment_for_principal(user) \
			 if user is not None and enrollments is not None else None
	return record
			
def is_enrolled(context, user):
	record = get_enrollment_record(context, user)
	return record is not None

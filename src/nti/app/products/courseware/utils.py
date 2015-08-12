#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
from itertools import chain
from datetime import datetime

from zope import component

from zope.component.interfaces import ComponentLookupError

from zope.security.interfaces import IPrincipal

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from zope.traversing.api import traverse

from nti.contenttypes.courses.interfaces import RID_TA
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from nti.contenttypes.courses import get_course_vendor_info
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager

from .enrollment import EnrollmentOptions
from .interfaces import IEnrollmentOptionProvider

ZERO_DATETIME = datetime.utcfromtimestamp(0)

def get_parent_course(context):
	course = ICourseInstance(context)
	if ICourseSubInstance.providedBy(course):
		course = course.__parent__.__parent__
	return course

def is_there_an_open_enrollment(course, user):
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,), main_course.SubInstances.values()):
			enrollments = ICourseEnrollments(instance)
			record = enrollments.get_enrollment_for_principal(user)
			if record is not None and record.Scope == ES_PUBLIC:
				return True
	return False

def get_enrollment_in_hierarchy(course, user):
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,), main_course.SubInstances.values()):
			enrollments = ICourseEnrollments(instance)
			record = enrollments.get_enrollment_for_principal(user)
			if record is not None:
				return record
	return None
get_any_enrollment = get_enrollment_in_hierarchy

def drop_any_other_enrollments(context, user, ignore_existing=True):
	course = ICourseInstance(context)
	entry = ICourseCatalogEntry(course)
	course_ntiid = entry.ntiid

	result = []
	main_course = get_parent_course(course)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			instance_entry = ICourseCatalogEntry(instance)
			if ignore_existing and course_ntiid == instance_entry.ntiid:
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
	prin = IPrincipal(user, None)
	course = ICourseInstance(context, None)
	roles = IPrincipalRoleMap(course, None)
	if roles and prin:
		result = Allow in (roles.getSetting(RID_TA, prin.id),
						   roles.getSetting(RID_INSTRUCTOR, prin.id))
	return result

def is_instructor_in_hierarchy(context, user):
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			if is_course_instructor(instance, user):
				return True
	return False

def get_instructed_course_in_hierarchy(context, user):
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			if is_course_instructor(instance, user):
				return instance
	return None

def get_catalog_entry(ntiid, safe=True):
	try:
		catalog = component.getUtility(ICourseCatalog)
		entry = catalog.getCatalogEntry(ntiid) if ntiid else None
		return entry
	except (ComponentLookupError, KeyError) as e:
		if not safe:
			raise e
	return None

def get_enrollment_record(context, user):
	course = ICourseInstance(context, None)
	enrollments = ICourseEnrollments(course, None)
	record = enrollments.get_enrollment_for_principal(user) \
			 if user is not None and enrollments is not None else None
	return record

def get_enrollment_record_in_hierarchy(context, user):
	main_course = get_parent_course(context)
	if main_course is not None:
		for instance in chain((main_course,) , main_course.SubInstances.values()):
			record = get_enrollment_record(instance, user)
			if record is not None:
				return record
	return None

def is_enrolled(context, user):
	record = get_enrollment_record(context, user)
	return record is not None

def is_enrolled_in_hierarchy(context, user):
	record = get_enrollment_record_in_hierarchy(context, user)
	return record is not None

def has_enrollments(user):
	for enrollments in component.subscribers((user,), IPrincipalEnrollments):
		if enrollments.count_enrollments():
			return True
	return False

def get_vendor_info(context):
	info = get_course_vendor_info(context, False)
	return info or {}

def get_enrollment_communities(context):
	vendor_info = get_vendor_info(context)
	result = traverse(vendor_info, 'NTI/Enrollment/Communities', default=False)
	if result and isinstance(result, six.string_types):
		result = [result,]
	return result

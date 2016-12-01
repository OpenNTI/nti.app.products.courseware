#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
from datetime import datetime
from collections import Mapping

from pyramid.threadlocal import get_current_request

from zope import component

from zope.intid.interfaces import IIntIds

from zope.traversing.api import traverse

from nti.app.assessment.common import get_evaluation_courses

from nti.app.products.courseware.enrollment import EnrollmentOptions

from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.app.products.courseware.invitations import CourseInvitation

from nti.app.products.courseware.utils.decorators import PreviewCourseAccessPredicateDecorator

from nti.assessment.interfaces import IQAssignment

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import SCOPE
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import DESCRIPTION

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

#: Default memcache expiration time
DEFAULT_EXP_TIME = 86400

#: 1970-01-1
ZERO_DATETIME = datetime.utcfromtimestamp(0)

# BWC exports
PreviewCourseAccessPredicate = PreviewCourseAccessPredicateDecorator

def get_vendor_info(context):
	info = get_course_vendor_info(context, False)
	return info or {}

def get_enrollment_options(context):
	result = EnrollmentOptions()
	entry = ICourseCatalogEntry(context)
	for provider in list(component.subscribers((entry,), IEnrollmentOptionProvider)):
		for option in provider.iter_options():
			result.append(option)
	return result

def get_enrollment_communities(context):
	vendor_info = get_vendor_info(context)
	result = traverse(vendor_info, 'NTI/Enrollment/Communities', default=False)
	if result and isinstance(result, six.string_types):
		result = result.split()
	return result or ()

def get_enrollment_courses(context):
	vendor_info = get_vendor_info(context)
	result = traverse(vendor_info, 'NTI/Enrollment/Courses', default=False)
	if result and isinstance(result, six.string_types):
		result = result.split()
	return result or ()

def get_enrollment_scopes(context):
	vendor_info = get_vendor_info(context)
	return traverse(vendor_info, 'NTI/Enrollment/Scopes', default=False)

def get_enrollment_for_scope(context, scope):
	scopes = get_enrollment_scopes(context)
	if isinstance(scopes, Mapping):
		result = scopes.get(scope)
		if result and isinstance(result, six.string_types):
			result = result.split()
		return result or ()
	return ()

def get_course_and_parent(context):
	return {ICourseInstance(context, None), get_parent_course(context)}

def get_vendor_thank_you_page(course, key):
	for course in get_course_and_parent(course):
		vendor_info = get_vendor_info(course)
		tracking = traverse(vendor_info, 'NTI/VendorThankYouPage', default=False)
		if tracking and key in tracking:
			return tracking.get(key)
	return None

def get_course_invitations(context):
	entry = ICourseCatalogEntry(context, None)
	if entry is None:
		return ()
	for course in get_course_and_parent(context):
		result = None
		vendor_info = get_vendor_info(course)
		invitations = traverse(vendor_info, 'NTI/Invitations', default=False)
		# simple string code
		if isinstance(invitations, six.string_types):
			invitations = invitations.split()
		if isinstance(invitations, (list, tuple)):
			result = []
			for value in invitations:
				# simple string code
				if isinstance(value, six.string_types):
					invitaion = CourseInvitation(Code=value,
												 Scope=ES_PUBLIC,
												 Course=entry.ntiid,
												 Description=ES_PUBLIC)
					result.append(invitaion)
				# fully modeled invitation
				elif isinstance(value, Mapping):
					value = CaseInsensitiveDict(value)
					code = value.get('Code')
					scope = value.get(SCOPE) or ES_PUBLIC
					desc = value.get(DESCRIPTION) or scope
					isGeneric = is_true(value.get('IsGeneric'))
					if code:
						invitaion = CourseInvitation(Code=code,
												 	 Scope=scope,
												 	 Description=desc,
												 	 Course=entry.ntiid,
												 	 IsGeneric=isGeneric)
						result.append(invitaion)
		if result:
			return result
	return ()

def get_course_invitation(context, code):
	for invitation in get_course_invitations(context):
		if invitation.Code == code:
			return invitation
	return None

def has_course_invitations(context):
	result = get_course_invitations(context)
	return bool(result)

def _search_for_lessons(evaluation, provided, container_ntiids, catalog,
						valid_outlines, intids, sites):
	"""
	Find lessons for the given evaluation, existing in our valid_outlines.
	"""
	results = []
	for item in catalog.search_objects(intids=intids,
									   provided=provided,
									   container_ntiids=container_ntiids,
									   container_all_of=False,
									   sites=sites):
		if item.target == evaluation.ntiid:
			lesson = find_interface(item, INTILessonOverview, strict=False)
			if lesson is not None:
				outline = find_interface(lesson, ICourseOutline, strict=False)
				if outline is not None and outline in valid_outlines:
					results.append(lesson)
	return results

def _get_lessons_for_courses(container_ntiids):
	"""
	Find lessons for the given evaluation, existing in our valid_outlines.
	"""
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	sites = get_component_hierarchy_names()
	result_set = catalog.search_objects(intids=intids,
										provided=INTILessonOverview,
										container_ntiids=container_ntiids,
										container_all_of=False,
										sites=sites)
	return set(result_set) if result_set else ()

def _get_course_ntiids(courses):
	# Get any courses that match our outline; since the ref may have been
	# indexed or stored from any course.
	results = set()
	for course in courses or ():
		hierarchy = get_course_hierarchy(course)
		root_outline = course.Outline
		# outlines.add( root_outline )
		for child_course in hierarchy or ():
			if child_course.Outline == root_outline:
				entry = ICourseCatalogEntry(child_course, None)
				if entry is not None:
					results.add(entry.ntiid)
	return results

def _is_evaluation_in_lesson(lesson, target_ntiids, outline_provided):
	for group in lesson or ():
		for item in group or ():
			if 		outline_provided.providedBy(item) \
				and item.target in target_ntiids:
				return True
	return False

def _get_ref_target_ntiids(evaluation):
	result = []
	if IQAssignment.providedBy(evaluation):
		# Some refs actually point to assignment qset ntiids.
		for part in evaluation.parts or ():
			if part.question_set is not None:
				result.append(part.question_set.ntiid)
	result.append(evaluation.ntiid)
	return result

def get_evaluation_lessons(evaluation, outline_provided, courses=None, request=None):
	"""
	For the given evaluation, get all lessons containing the evaluation.

	`outline_provided` is the outline ref type pointing to the given evaluation.
	"""
	request = get_current_request() if request is None else request
	if courses is None:
		# XXX: If we have a request course, we use it. Do we want all courses?
		course = ICourseInstance(request, None)
		courses = (course,)
		if course is None:
			courses = get_evaluation_courses(evaluation)
	target_ntiids = _get_ref_target_ntiids(evaluation)
	container_ntiids = _get_course_ntiids(courses)
	lessons = _get_lessons_for_courses(container_ntiids)
	result = set()
	for lesson in lessons:
		if _is_evaluation_in_lesson(lesson, target_ntiids, outline_provided):
			result.add(lesson)
	return result

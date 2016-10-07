#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
import hashlib
from datetime import datetime
from collections import Mapping

import repoze.lru

from pyramid.threadlocal import get_current_request

from zope import component

from zope.intid.interfaces import IIntIds

from zope.traversing.api import traverse
from zope.traversing.interfaces import IEtcNamespace

from nti.app.assessment.common import get_evaluation_courses

from nti.app.products.courseware.enrollment import EnrollmentOptions

from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.app.products.courseware.invitations import CourseInvitation

from nti.app.products.courseware.utils.decorators import PreviewCourseAccessPredicateDecorator

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.common.maps import CaseInsensitiveDict

from nti.common.string import is_true

from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import SCOPE
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import DESCRIPTION

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import IMemcacheClient

from nti.externalization.oids import to_external_ntiid_oid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

# : Default memcache expiration time
DEFAULT_EXP_TIME = 86400

# : 1970-01-1
ZERO_DATETIME = datetime.utcfromtimestamp(0)

# BWC exports
PreviewCourseAccessPredicate = PreviewCourseAccessPredicateDecorator

def last_synchronized(context=None):
	if context is None:
		context = component.queryUtility(IEtcNamespace, name='hostsites')
	result = getattr(context, 'lastSynchronized', None) or 0
	return result

def memcache_client():
	return component.queryUtility(IMemcacheClient)

def memcache_get(key, client=None):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			return client.get(key)
		except Exception:
			pass
	return None

def memcache_set(key, value, client=None, exp=DEFAULT_EXP_TIME):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			client.set(key, value, time=exp)
			return True
		except Exception:
			pass
	return False

@repoze.lru.lru_cache(200)
def encode_keys(*keys):
	result = hashlib.md5()
	for key in keys:
		result.update(str(key).lower())
	return result.hexdigest()

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

def _search_for_lessons(evaluation, provided, container_ntiids, catalog, intids, sites):
	results = []
	for item in catalog.search_objects(intids=intids,
									   provided=provided,
									   container_ntiids=container_ntiids,
									   container_all_of=False,
									   sites=sites):
		if item.target == evaluation.ntiid:
			lesson = find_interface(item, INTILessonOverview, strict=False)
			if lesson is not None:
				results.append(lesson)
	return results

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
	catalog = get_library_catalog()
	intids = component.getUtility(IIntIds)
	sites = get_component_hierarchy_names()
	container_ntiids = \
			set(getattr(ICourseCatalogEntry(x, None), 'ntiid', None) for x in courses)
	container_ntiids.discard(None)
	result = _search_for_lessons(evaluation, outline_provided,
								  container_ntiids, catalog, intids, sites)
	return result

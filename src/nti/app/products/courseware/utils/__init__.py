#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import six
import hashlib
from datetime import datetime
from collections import Mapping

import repoze.lru

from zope import component

from zope.traversing.api import traverse
from zope.traversing.interfaces import IEtcNamespace

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.enrollment import EnrollmentOptions

from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.app.products.courseware.utils.decorators import PreviewCourseAccessPredicateDecorator

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import SCOPE
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import DESCRIPTION

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.utils import get_parent_course

from nti.dataserver.interfaces import IMemcacheClient

from nti.externalization.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface

#: Default memcache expiration time
DEFAULT_EXP_TIME = 86400

#: 1970-01-1
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

def get_vendor_thank_you_page(course, key):
	for course in {ICourseInstance(course, None), get_parent_course(course)}:
		vendor_info = get_vendor_info(course)
		tracking = traverse(vendor_info, 'NTI/VendorThankYouPage', default=False)
		if tracking and key in tracking:
			return tracking.get(key)
	return None

def get_course_invitations(context):
	for course in {ICourseInstance(context, None), get_parent_course(context)}:
		result = None
		vendor_info = get_vendor_info(course)
		invitations = traverse(vendor_info, 'NTI/Invitations', default=False)
		if isinstance(invitations, six.string_types):
			invitations = invitations.split()
		if isinstance(invitations, (list, tuple)):
			result = []
			for value in invitations:
				if isinstance(value, six.string_types):
					result.append({'code':value, SCOPE:ES_PUBLIC, DESCRIPTION:ES_PUBLIC})
				elif isinstance(invitations, Mapping):
					value = CaseInsensitiveDict(value)
					code = value.get('code')
					scope = value.get(SCOPE) or ES_PUBLIC
					desc = value.get(DESCRIPTION) or scope
					if code:
						result.append({'code':code, SCOPE:scope, DESCRIPTION:desc})
		elif isinstance(invitations, Mapping):
			result = []
			for key, value in invitations.items():
				if isinstance(value, six.string_types):
					result.append({'code':key, SCOPE:value, DESCRIPTION:value})
				elif isinstance(value, Mapping):
					value = CaseInsensitiveDict(value)
					scope = value.get(SCOPE) or ES_PUBLIC
					desc = value.get(DESCRIPTION) or scope
					result.append({'code':key, SCOPE:scope, DESCRIPTION:desc})
		if result:
			return result
	return None

def get_course_invitation(code):
	result = component.queryUtility(IJoinCourseInvitation, name=code or '')
	return result

def get_all_course_invitations():
	result = list(x for _, x in component.getUtilitiesFor(IJoinCourseInvitation))
	return result

def get_invitations_for_course(context):
	result = {}
	course = ICourseInstance(context, None)
	entry = ICourseCatalogEntry(course, None)
	entry_ntiid = entry.ntiid if entry is not None else None
	ntiid = to_external_ntiid_oid(course) if course is not None else None
	for name, invitation in list(component.getUtilitiesFor(IJoinCourseInvitation)):
		if invitation.course in (ntiid, entry_ntiid):
			result[name] = invitation
	return result

def has_course_invitations(context):
	result = get_invitations_for_course(context)
	return len(result) >= 1

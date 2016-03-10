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

import repoze.lru

from zope import component

from zope.traversing.api import traverse
from zope.traversing.interfaces import IEtcNamespace

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.enrollment import EnrollmentOptions

from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.app.products.courseware.utils.decorators import PreviewCourseAccessPredicateDecorator

from nti.contenttypes.courses import get_course_vendor_info

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_parent_course

from nti.dataserver.interfaces import IMemcacheClient

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
		except (StandardError, Exception):
			pass
	return None

def memcache_set(key, value, client=None, exp=DEFAULT_EXP_TIME):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			client.set(key, value, time=exp)
			return True
		except (StandardError, Exception):
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
	for provider in component.subscribers((entry,), IEnrollmentOptionProvider):
		for option in provider.iter_options():
			result.append(option)
	return result

def get_enrollment_communities(context):
	vendor_info = get_vendor_info(context)
	result = traverse(vendor_info, 'NTI/Enrollment/Communities', default=False)
	if result and isinstance(result, six.string_types):
		result = [result]
	return result

def get_enrollment_courses(context):
	vendor_info = get_vendor_info(context)
	result = traverse(vendor_info, 'NTI/Enrollment/Courses', default=False)
	if result and isinstance(result, six.string_types):
		result = [result]
	return result

def get_vendor_thank_you_page(course, key):
	for course in {ICourseInstance(course, None), get_parent_course(course)}:
		vendor_info = get_vendor_info(course)
		tracking = traverse(vendor_info, 'NTI/VendorThankYouPage', default=False)
		if tracking and key in tracking:
			return tracking.get(key)
	return None

def get_assets_folder(context, strict=True):
	course = ICourseInstance(context, None)
	if course is None:
		course = find_interface(context, ICourseInstance, strict=strict)
	root = ICourseRootFolder(course, None)
	if root is not None:
		if ASSETS_FOLDER not in root:
			result = CourseContentFolder(name=ASSETS_FOLDER)
			root[ASSETS_FOLDER] = result
		else:
			result = root[ASSETS_FOLDER]
		return result
	return None

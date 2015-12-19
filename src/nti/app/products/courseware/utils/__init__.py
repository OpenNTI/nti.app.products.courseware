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

import repoze.lru

from zope import component
from zope import interface

from zope.intid import IIntIds

from zope.security.interfaces import IPrincipal

from zope.traversing.api import traverse
from zope.traversing.interfaces import IEtcNamespace

from nti.contentfolder.model import ContentFolder

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import EDITOR
from nti.contenttypes.courses.interfaces import INSTRUCTOR

from nti.contenttypes.courses import get_course_vendor_info
from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import IMemcacheClient

from nti.site.site import get_component_hierarchy_names

from ..enrollment import EnrollmentOptions

from ..interfaces import IUserAdministeredCourses
from ..interfaces import IEnrollmentOptionProvider

from .course_migrator import migrate as course_migrator

from nti.traversal.traversal import find_interface

from ..interfaces import ICourseRootFolder

from .. import ASSETS_FOLDER

DEFAULT_EXP_TIME = 86400

ZERO_DATETIME = datetime.utcfromtimestamp(0)

def last_synchronized():
	hostsites = component.queryUtility(IEtcNamespace, name='hostsites')
	result = getattr(hostsites, 'lastSynchronized', 0)
	return result

def memcache_client():
	return component.queryUtility(IMemcacheClient)

def memcache_get(key, client=None):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			return client.get(key)
		except:
			pass
	return None

def memcache_set(key, value, client=None, exp=DEFAULT_EXP_TIME):
	client = component.queryUtility(IMemcacheClient) if client is None else client
	if client is not None:
		try:
			client.set(key, value, time=exp)
			return True
		except:
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

@interface.implementer(IUserAdministeredCourses)
class IndexAdminCourses(object):

	def iter_admin(self, user):
		intids = component.getUtility(IIntIds)
		catalog = get_enrollment_catalog()
		sites = get_component_hierarchy_names()
		username = getattr(user, 'username', user)
		query = {
			IX_SITE:{'any_of': sites},
			IX_SCOPE: {'any_of':(INSTRUCTOR, EDITOR)},
			IX_USERNAME:{'any_of':(username,)},
		}
		for uid in catalog.apply(query) or ():
			context = intids.queryObject(uid)
			if ICourseInstance.providedBy(context):  # extra check
				yield context

@interface.implementer(IUserAdministeredCourses)
class IterableAdminCourses(object):

	def iter_admin(self, user):
		principal = IPrincipal(user)
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			instance = ICourseInstance(entry)
			if principal in instance.instructors:
				yield instance

def get_assets_folder(context, strict=True):
	course = ICourseInstance(context, None)
	if course is None:
		course = find_interface(context, ICourseInstance, strict=strict)
	root = ICourseRootFolder(course, None)
	if root is not None:
		if ASSETS_FOLDER not in root:
			result = ContentFolder(name=ASSETS_FOLDER)
			root[ASSETS_FOLDER] = result
		else:
			result = root[ASSETS_FOLDER]
		return result
	return None

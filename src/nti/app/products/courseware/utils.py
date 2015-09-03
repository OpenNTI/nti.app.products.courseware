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

from zope import component
from zope import interface

from zope.intid import IIntIds

from zope.security.interfaces import IPrincipal

from zope.traversing.api import traverse

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import INSTRUCTOR

from nti.contenttypes.courses import get_course_vendor_info
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.site.site import get_component_hierarchy_names

from .enrollment import EnrollmentOptions

from .interfaces import IUserAdministeredCourses
from .interfaces import IEnrollmentOptionProvider

ZERO_DATETIME = datetime.utcfromtimestamp(0)

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

@interface.implementer(IUserAdministeredCourses)
class IndexAdminCourses(object):

	def iter_admin(self, user):
		intids = component.getUtility(IIntIds)
		catalog = get_enrollment_catalog()
		sites = get_component_hierarchy_names()
		username = getattr(user, 'username', user)
		query = {
			IX_SITE:{'any_of': sites},
			IX_SCOPE: {'any_of':(INSTRUCTOR,)},
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

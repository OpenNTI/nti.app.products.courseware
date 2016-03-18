#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from nti.app.products.courseware.resources import RESOURCES

from nti.app.products.courseware.resources.filer import CourseSourceFiler

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler

from nti.app.products.courseware.resources.model import CourseRootFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

@component.adapter(ICourseInstance)
@interface.implementer(ICourseRootFolder)
def course_resources(course, create=True):
	result = None
	annotations = IAnnotations(course)
	try:
		KEY = RESOURCES
		result = annotations[KEY]
	except KeyError:
		if create:
			result = CourseRootFolder(name=RESOURCES)
			annotations[KEY] = result
			result.__name__ = KEY
			result.__parent__ = course
	if result.creator is not None:
		result.creator = SYSTEM_USER_ID
	return result
_course_resources = course_resources

def _resources_for_course_path_adapter(context, request):
	course = ICourseInstance(context)
	return _course_resources(course)

def _course_user_source_filer(context, user=None):
	course = ICourseInstance(context)
	result = CourseSourceFiler(course, user)
	return result

@component.adapter(ICourseInstance)
@interface.implementer(ICourseSourceFiler)
def _course_source_filer(context):
	return _course_user_source_filer(context, None)



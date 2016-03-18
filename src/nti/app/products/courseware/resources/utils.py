#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.base.abstract_views import get_source_filer

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.traversal.traversal import find_interface

def get_course(context, strict=False):
	course = ICourseInstance(context, None)
	if course is None:
		course = find_interface(context, ICourseInstance, strict=strict)
	return course

def get_assets_folder(context, strict=True):
	course = get_course(context, strict=strict)
	root = ICourseRootFolder(course, None)
	if root is not None:
		if ASSETS_FOLDER not in root:
			result = CourseContentFolder(name=ASSETS_FOLDER)
			root[ASSETS_FOLDER] = result
		else:
			result = root[ASSETS_FOLDER]
		if result.creator is None:
			result.creator = SYSTEM_USER_ID
		return result
	return None

def get_course_filer(context, user=None):
	course = get_course(context, strict=False)
	result = get_source_filer(course, user, ICourseSourceFiler)
	return result

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.app.products.courseware import ASSETS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.traversal.traversal import find_interface

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

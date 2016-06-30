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

from zope.security.interfaces import IPrincipal

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_editors

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.traversal.traversal import find_interface

@component.adapter(ICourseRootFolder)
@interface.implementer(IACLProvider)
class CourseRootFolderACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	@Lazy
	def __acl__(self):
		aces = [ ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, self),
				 ace_allowing(ROLE_CONTENT_EDITOR, ALL_PERMISSIONS, type(self))]

		course = find_interface(self.context, ICourseInstance, strict=False)
		if course is not None:
			# give instructors special powers
			aces.extend(ace_allowing(i, ALL_PERMISSIONS, type(self))
						for i in course.instructors or ())

			for i in get_course_editors(course):
				aces.append(ace_allowing(i, ALL_PERMISSIONS, type(self)))

			# all scopes have read access
			course.initScopes()
			for scope in course.SharingScopes:
				aces.append(ace_allowing(IPrincipal(scope), ACT_READ, type(self)))

			if ICourseSubInstance.providedBy(course):
				parent = get_parent_course(course)
				for i in parent.instructors or ():
					aces.append(ace_allowing(i, ACT_READ, type(self)))
				for i in get_course_editors(parent):
					aces.append(ace_allowing(i, ACT_READ, type(self)))

		result = acl_from_aces(aces)
		return result

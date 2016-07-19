#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from itertools import chain

from zope import component
from zope import interface

from zope.security.interfaces import IPrincipal

from nti.app.contentfile.acl import ContentBaseFileACLProvider

from nti.app.contentfolder.acl import ContentFolderACLProvider

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseLockedFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_editors

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_UPDATE
from nti.dataserver.authorization import ROLE_ADMIN
from nti.dataserver.authorization import ROLE_CONTENT_EDITOR

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_denying_all

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.traversal.traversal import find_interface

def _common_aces(course, aces):
	# all scopes have read access
	course.initScopes()
	for scope in course.SharingScopes:
		aces.append(ace_allowing(IPrincipal(scope), ACT_READ, type(self)))

	if ICourseSubInstance.providedBy(course):
		parent = get_parent_course(course)
		for i in chain(parent.instructors or (), get_course_editors(parent)):
			aces.append(ace_allowing(i, ACT_READ, type(self)))

@interface.implementer(IACLProvider)
@component.adapter(ICourseRootFolder)
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

		course = find_interface(self.context, ICourseInstance, strict=True)
		for i in chain(course.instructors or (), get_course_editors(course)):
			aces.append(ace_allowing(i, ALL_PERMISSIONS, type(self)))

		_common_aces(course, aces)

		result = acl_from_aces(aces)
		return result

@interface.implementer(IACLProvider)
@component.adapter(ICourseLockedFolder)
class CourseLockedFolderACLProvider(object):

	def __init__(self, context):
		self.context = context

	@property
	def __parent__(self):
		return self.context.__parent__

	def principals_and_perms(self, course):
		yield ROLE_CONTENT_EDITOR, (ACT_READ, ACT_UPDATE)

		for i in chain(course.instructors or (), get_course_editors(course)):
			yield i, (ACT_READ, ACT_UPDATE)

		course.initScopes()
		for scope in course.SharingScopes:
			yield IPrincipal(scope), (ACT_READ,)

		if ICourseSubInstance.providedBy(course):
			parent = get_parent_course(course)
			for i in chain(parent.instructors or (), get_course_editors(parent)):
				yield i, (ACT_READ,)

	@Lazy
	def __acl__(self):
		aces = [ ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS, self) ]
		course = find_interface(self.context, ICourseInstance, strict=True)
		for i, perms in self.principals_and_perms(course):
			for perm in perms:
				aces.append(ace_allowing(i, perm, type(self)))
		aces.append(ace_denying_all())
		result = acl_from_aces(aces)
		return result

@interface.implementer(IACLProvider)
@component.adapter(ICourseContentFolder)
class CourseContentFolderACLProvider(ContentFolderACLProvider):

	@Lazy
	def __acl__(self):
		aces = super(CourseContentFolderACLProvider, self).__aces__
		course = find_interface(self.context, ICourseInstance, strict=True)
		for i in chain(course.instructors or (), get_course_editors(course)):
			aces.append(ace_allowing(i, ALL_PERMISSIONS, type(self)))

		_common_aces(course, aces)

		result = acl_from_aces(aces)
		return result

@interface.implementer(IACLProvider)
@component.adapter(ICourseContentFile)
class CourseContentFileACLProvider(ContentBaseFileACLProvider):

	@Lazy
	def __acl__(self):
		aces = super(CourseContentFileACLProvider, self).__aces__
		course = find_interface(self.context, ICourseInstance, strict=True)
		for i in chain(course.instructors or (), get_course_editors(course)):
			aces.append(ace_allowing(i, ALL_PERMISSIONS, type(self)))

		_common_aces(course, aces)

		result = acl_from_aces(aces)
		return result

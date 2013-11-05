#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of an Atom/OData workspace and collection
for courses.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope import location

from . import interfaces
from nti.appserver import interfaces as app_interfaces

from nti.utils.property import alias

@interface.implementer(interfaces.ICoursesWorkspace)
class _CoursesWorkspace(location.Location):

	__name__ = 'Courses'
	name = alias('__name__')

	def __init__(self, user_service):
		self.context = user_service
		self.user = user_service.user

	@property
	def collections(self):
		"""
		The collections in a course provide info about the enrolled and available
		courses.
		"""
		return (AllCoursesCollection(self),
				EnrolledCoursesCollection(self))

@interface.implementer(interfaces.ICoursesWorkspace)
@component.adapter(app_interfaces.IUserService)
def CoursesWorkspace( user_service ):
	"""
	The courses for a user reside at the path ``/users/$ME/Courses``.
	"""
	catalog = component.queryUtility( interfaces.ICourseCatalog )
	if catalog:
		# Ok, patch up the parent relationship
		workspace = _CoursesWorkspace( user_service )
		workspace.__parent__ = workspace.user
		return workspace

@interface.implementer(app_interfaces.ICollection)
class AllCoursesCollection(location.Location):

	__name__ = 'AllCourses'
	name = alias('__name__')

	def __init__(self, parent):
		self.__parent__ = parent

	accepts = ()

@interface.implementer(app_interfaces.ICollection)
class EnrolledCoursesCollection(location.Location):

	__name__ = 'EnrolledCourses'
	name = alias('__name__')

	def __init__(self, parent):
		self.__parent__ = parent

	accepts = ()
	# TODO: Enroll by pasting to this collection?
	# Or some href on the course info itself?

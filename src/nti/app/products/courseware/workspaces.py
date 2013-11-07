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
from zope.container import contained

from . import interfaces
from nti.appserver import interfaces as app_interfaces

from nti.utils.property import alias

@interface.implementer(interfaces.ICoursesWorkspace)
class _CoursesWorkspace(contained.Contained):

	__name__ = 'Courses'
	name = alias('__name__')

	def __init__(self, user_service, catalog):
		self.context = user_service
		self.user = user_service.user
		self.catalog = catalog

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
		workspace = _CoursesWorkspace( user_service, catalog )
		workspace.__parent__ = workspace.user
		return workspace

@interface.implementer(app_interfaces.IContainerCollection)
class AllCoursesCollection(contained.Contained):

	__name__ = 'AllCourses'
	name = alias('__name__')

	def __init__(self, parent):
		self.__parent__ = parent
		self.container = parent.catalog

	accepts = ()

from nti.dataserver.datastructures import LastModifiedCopyingUserList
@interface.implementer(app_interfaces.IContainerCollection)
class EnrolledCoursesCollection(contained.Contained):

	__name__ = 'EnrolledCourses'
	name = alias('__name__')

	def __init__(self, parent):
		self.__parent__ = parent
		self.container = LastModifiedCopyingUserList()
		for catalog in component.subscribers( (parent.user,), interfaces.IPrincipalEnrollmentCatalog ):
			enrolled = catalog.iter_enrollments()
			self.container.updateLastModIfGreater( getattr( enrolled, 'lastModified', 0) )
			self.container.extend( [interfaces.ICourseCatalogEntry(x)
									for x in enrolled] )

	accepts = ()
	# TODO: Enroll by POSTing to this collection?
	# Or some href on the course info itself?

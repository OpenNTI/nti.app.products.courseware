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
from zope.location.traversing import LocationPhysicallyLocatable

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
			self.container.extend( enrolled )

	accepts = ()
	# TODO: Enroll by POSTing to this collection?
	# Or some href on the course info itself?

from pyramid.threadlocal import get_current_request
from pyramid.security import authenticated_userid
from nti.dataserver.users import User
from nti.dataserver.interfaces import IDataserver
from zope.location.interfaces import IRoot
from zope.location.interfaces import ILocationInfo

@component.adapter(interfaces.ICourseCatalogEntry)
class CatalogEntryLocationInfo(LocationPhysicallyLocatable):
	"""
	We make catalog entries always appear relative to the
	user if a request is in progress.
	"""

	def getParents(self):
		entry = self.context
		catalog = entry.__parent__
		ds = component.getUtility(IDataserver)

		parents = [catalog]

		request = get_current_request()
		userid = authenticated_userid(request)

		if userid:

			user = User.get_user( userid, dataserver=ds )
			service = app_interfaces.IUserService(user)
			workspace = CoursesWorkspace(service)
			all_courses = AllCoursesCollection(workspace)

			parents.append( all_courses )
			parents.append( workspace )
			parents.append( user )
			parents.extend( ILocationInfo(user).getParents() )

		else:
			parents.append( ds.dataserver_folder )
			parents.extend( ILocationInfo(ds.dataserver_folder).getParents() )


		if not IRoot.providedBy(parents[-1]):
			raise TypeError("Not enough context to get all parents")

		return parents

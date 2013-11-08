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

	def __getitem__(self, key):
		"Make us traversable to collections."
		for i in self.collections:
			if i.__name__ == key:
				return i
		raise KeyError(key)

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

	def __getitem__(self, key):
		"We can be traversed to the CourseCatalog."
		if key == self.container.__name__:
			return self.container
		raise KeyError(key)

from nti.dataserver.datastructures import LastModifiedCopyingUserList
@interface.implementer(interfaces.IEnrolledCoursesCollection)
class EnrolledCoursesCollection(contained.Contained):

	__name__ = 'EnrolledCourses'
	name = alias('__name__')

	def __init__(self, parent):
		self.__parent__ = parent
		self.container = LastModifiedCopyingUserList()
		for catalog in component.subscribers( (parent.user,), interfaces.IPrincipalEnrollmentCatalog ):
			enrolled = catalog.iter_enrollments()
			self.container.extend( enrolled )

	# TODO: Need to add an accepts for what the
	# POST-to-enroll takes
	accepts = ()

	#def __getitem__(self,key):
	#	"our children are our enrolled courses"
	#	return self.__parent__.catalog[key]

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

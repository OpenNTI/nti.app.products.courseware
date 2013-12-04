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
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.interfaces import IUser

from nti.utils.property import Lazy
from nti.utils.property import alias

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing


@interface.implementer(interfaces.ICoursesWorkspace)
class _CoursesWorkspace(contained.Contained):

	#: Our name, part of our URL
	__name__ = 'Courses'
	name = alias('__name__', __name__)

	def __init__(self, user_service, catalog):
		self.context = user_service
		self.user = user_service.user
		self.catalog = catalog

	@Lazy
	def collections(self):
		"""
		The collections in this workspace provide info about the enrolled and
		available courses as well as any courses the user administers (teaches).
		"""
		return (AllCoursesCollection(self),
				EnrolledCoursesCollection(self),
				AdministeredCoursesCollection(self))

	def __getitem__(self, key):
		"Make us traversable to collections."
		for i in self.collections:
			if i.__name__ == key:
				return i
		raise KeyError(key)

	def __len__(self):
		return len(self.collections)

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

	#: Our name, part of our URL.
	__name__ = 'AllCourses'

	name = alias('__name__',__name__)

	def __init__(self, parent):
		self.__parent__ = parent
		self.container = parent.catalog

	accepts = ()

	def __getitem__(self, key):
		"We can be traversed to the CourseCatalog."
		if key == self.container.__name__:
			return self.container
		raise KeyError(key)

	def __len__(self):
		return 1

from nti.dataserver.datastructures import LastModifiedCopyingUserList

class _AbstractQueryBasedCoursesCollection(contained.Contained):
	"""
	Performs subscription-adapter based queries to find
	the eligible objects.
	"""

	query_interface = None
	query_attr = None
	contained_interface = None
	user_extra_auth = None

	accepts = ()

	def __init__(self, parent):
		self.__parent__ = parent

	@Lazy
	def container(self):
		parent = self.__parent__
		container = LastModifiedCopyingUserList()
		for catalog in component.subscribers( (parent.user,), self.query_interface ):
			queried = getattr(catalog, self.query_attr)()
			container.extend( queried )
		# Now that we've got the courses, turn them into enrollment records;
		# using extend() above or the direct lists return by the iterator
		# preserves modification dates
		container[:] = [self.contained_interface(x) for x in container]
		for enrollment in container:
			enrollment.__parent__ = self
			if self.user_extra_auth:
				enrollment.__acl__ = acl_from_aces(ace_allowing(parent.user,
																self.user_extra_auth,
																type(self)))

		return container

	def __getitem__(self,key):
		for o in self.container:
			if o.__name__ == key or interfaces.ICourseCatalogEntry(o).__name__ == key:
				return o
		raise KeyError(key)

	def __len__(self):
		return len(self.container)

class _AbstractInstanceWrapper(contained.Contained):

	__acl__ = ()
	def __init__(self, context):
		self.CourseInstance = context

	@property
	def __name__(self):
		return self.CourseInstance.__name__

	def __conform__(self, iface):
		if iface.isOrExtends(ICourseInstance):
			return self.CourseInstance


@interface.implementer(interfaces.ICourseInstanceEnrollment)
@component.adapter(ICourseInstance)
class CourseInstanceEnrollment(_AbstractInstanceWrapper):
	pass

@interface.implementer(interfaces.ICourseCatalogEntry)
def wrapper_to_catalog(wrapper):
	return interfaces.ICourseCatalogEntry(wrapper.CourseInstance)

@interface.implementer(interfaces.IEnrolledCoursesCollection)
class EnrolledCoursesCollection(_AbstractQueryBasedCoursesCollection):

	#: Our name, part of our URL.
	__name__ = 'EnrolledCourses'
	name = alias('__name__',__name__)

	# TODO: Need to add an accepts for what the
	# POST-to-enroll takes. For now, just generic
	accepts = ("application/json",)

	query_interface = interfaces.IPrincipalEnrollmentCatalog
	query_attr = 'iter_enrollments'
	contained_interface = interfaces.ICourseInstanceEnrollment
	user_extra_auth = ACT_DELETE

@interface.implementer(interfaces.ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(SchemaConfigured,
									   _AbstractInstanceWrapper):
	createDirectFieldProperties(interfaces.ICourseInstanceAdministrativeRole)

@interface.implementer(interfaces.IPrincipalAdministrativeRoleCatalog)
@component.adapter(IUser)
class _DefaultPrincipalAdministrativeRoleCatalog(object):
	"""
	This catalog simply scans all available courses and checks
	to see if the user is in the instructors list.
	"""

	def __init__(self, user):
		self.user = user

	def iter_administrations(self):
		catalog = component.queryUtility( interfaces.ICourseCatalog )
		if catalog:
			for entry in catalog:
				instance = ICourseInstance(entry)
				if self.user in instance.instructors:
					yield CourseInstanceAdministrativeRole(RoleName='instructor',
														   CourseInstance=instance )

@interface.implementer(interfaces.IAdministeredCoursesCollection)
class AdministeredCoursesCollection(_AbstractQueryBasedCoursesCollection):

	#: Our name, part of our URL.
	__name__ = 'AdministeredCourses'
	name = alias('__name__',__name__)

	query_interface = interfaces.IPrincipalAdministrativeRoleCatalog
	query_attr = 'iter_administrations'
	contained_interface = interfaces.ICourseInstanceAdministrativeRole



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

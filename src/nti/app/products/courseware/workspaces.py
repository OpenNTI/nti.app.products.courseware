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

import operator

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

from nti.dataserver.authorization_acl import has_permission
from nti.dataserver.authorization import ACT_READ

@interface.implementer(app_interfaces.IContainerCollection)
class AllCoursesCollection(contained.Contained):

	#: Our name, part of our URL.
	__name__ = 'AllCourses'

	name = alias('__name__',__name__)

	def __init__(self, parent):
		self.__parent__ = parent
		# To support ACLs limiting the available parts of the catalog,
		# we filter out here.
		# we could do this with a proxy, but it's easier right now
		# just to copy. This is highly dependent on implementation
		self.container = type(parent.catalog)()
		self.container.__name__ = parent.catalog.__name__
		self.container.__parent__ = parent.catalog.__parent__
		self.container._entries = [x for x in parent.catalog if has_permission(ACT_READ, x, parent.user)]
		# We sort the entries to be sure that we get consistent order
		# across machines and restarts. This helps the ETag be more reliable
		self.container._entries.sort(key=operator.attrgetter('__name__'))

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
			# The adapter (contained_interface) rarely sets these
			# because it may not have them, so provide them ourself
			# TODO: Change the calling conventions so we don't have to do this
			if getattr(enrollment, 'Username', self) is None:
				enrollment.Username = parent.user.username
			if getattr(enrollment, '_user', self) is None:
				enrollment._user = parent.user

			if self.user_extra_auth:
				course = ICourseInstance(enrollment)
				enrollment._user = parent.user
				enrollment.__acl__ = acl_from_aces(ace_allowing(parent.user,
																self.user_extra_auth,
																type(self)))
				enrollment.__acl__.extend((ace_allowing( i, ACT_READ, type(self))
										   for i in course.instructors) )

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
		# Sometimes the CourseInstance object goes away
		# for externalization, so capture an extra copy
		self._private_course_instance = context

	@Lazy
	def __name__(self):
		return self._private_course_instance.__name__

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			return self._private_course_instance


@interface.implementer(interfaces.ICourseInstanceEnrollment)
@component.adapter(ICourseInstance)
class CourseInstanceEnrollment(_AbstractInstanceWrapper):
	__external_can_create__ = False
	Username = None
	_user = None

	def __init__(self, course, user=None):
		super(CourseInstanceEnrollment,self).__init__(course)
		if user:
			self.Username = user.username
			self._user = user

	def xxx_fill_in_parent(self):
		service = app_interfaces.IUserService(self._user)
		ws = interfaces.ICoursesWorkspace(service)
		enr_coll = EnrolledCoursesCollection(ws)
		self.__parent__ = enr_coll
		getattr(self, '__name__') # ensure we have this

	def __conform__(self, iface):
		if IUser.isOrExtends(iface):
			return self._user
		return super(CourseInstanceEnrollment, self).__conform__(iface)

from .interfaces import ILegacyCommunityBasedCourseInstance

@interface.implementer(interfaces.ILegacyCourseInstanceEnrollment)
@component.adapter(ILegacyCommunityBasedCourseInstance)
class LegacyCourseInstanceEnrollment(CourseInstanceEnrollment):
	__external_class_name__ = 'CourseInstanceEnrollment'


	def __init__(self, *args, **kwargs):
		super(LegacyCourseInstanceEnrollment,self).__init__(*args, **kwargs)

	@Lazy
	def LegacyEnrollmentStatus(self):
		course_inst = self._private_course_instance
		# check user belongs to restricted entity
		for_credit = self._user in course_inst.restricted_scope_entity_container
		return "ForCredit" if for_credit else "Open"


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

	def __init__(self, CourseInstance=None, RoleName=None):
		# SchemaConfigured is not cooperative
		SchemaConfigured.__init__(self, RoleName=RoleName)
		_AbstractInstanceWrapper.__init__(self, CourseInstance)

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
		userid = request.authenticated_userid if request else None

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


from nti.app.notabledata.interfaces import IUserPresentationPriorityCreators

@interface.implementer(IUserPresentationPriorityCreators)
@component.adapter(IUser, interface.Interface)
class _UserInstructorsPresentationPriorityCreators(object):
	"""
	The instructors of the classes a user is enrolled in are
	given priority.
	"""

	def __init__(self, user, request):
		self.context = user

	def iter_priority_creator_usernames(self):
		for enrollments in component.subscribers( (self.context,),
												  interfaces.IPrincipalEnrollmentCatalog):
			for enrollment in enrollments.iter_enrollments():
				course = ICourseInstance(enrollment)
				for instructor in course.instructors:
					yield instructor.id

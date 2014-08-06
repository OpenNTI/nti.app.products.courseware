#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of an Atom/OData workspace and collection
for courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component
from zope.container import contained
from zope.location.traversing import LocationPhysicallyLocatable

from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

from zope.securitypolicy.interfaces import IPrincipalRoleMap
from zope.securitypolicy.interfaces import Allow

from . import interfaces
from nti.appserver import interfaces as app_interfaces
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.dataserver.interfaces import IUser

from nti.utils.property import Lazy
from nti.utils.property import alias

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

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
	catalog = component.queryUtility( ICourseCatalog )
	if catalog is not None:
		# Ok, patch up the parent relationship
		workspace = _CoursesWorkspace( user_service, catalog )
		workspace.__parent__ = workspace.user
		return workspace

# XXX: We'd like to be able to use nti.appserver.pyramid_authorization:is_readable
# here because of all the caching it can do, but we are passing in an
# arbitrary user.
from nti.dataserver.authorization_acl import has_permission
from nti.dataserver.authorization import ACT_READ
from nti.externalization.interfaces import LocatedExternalDict
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance

@interface.implementer(app_interfaces.IContainerCollection)
class AllCoursesCollection(contained.Contained):

	#: Our name, part of our URL.
	__name__ = 'AllCourses'

	name = alias('__name__',__name__)

	class _IteratingDict(LocatedExternalDict):
		# BWC : act like a dict, but iterate like a list

		_v_container_ext_as_list = True
		def __iter__(self):
			return iter(self.values())

	def __init__(self, parent):
		self.__parent__ = parent
		user = parent.user
		# To support ACLs limiting the available parts of the catalog,
		# we filter out here.
		# we could do this with a proxy, but it's easier right now
		# just to copy. This is highly dependent on implementation.
		# We also filter out sibling courses when we are already enrolled
		# in one; this is probably inefficient
		container = self.container = self._IteratingDict()
		container.__name__ = parent.catalog.__name__
		container.__parent__ = parent.catalog.__parent__
		container.lastModified = parent.catalog.lastModified

		my_enrollments = {}
		for x in parent.catalog.iterCatalogEntries():
			if has_permission(ACT_READ, x, user):
				# Note that we have to expose these by NTIID, not their
				# __name__. Because the catalog can be reading from
				# multiple different sources, the __names__ might overlap

				course = ICourseInstance(x, None)
				if course is not None:
					enrollments = ICourseEnrollments(course)
					if enrollments.get_enrollment_for_principal(user) is not None:
						my_enrollments[x.ntiid] = course

				container[x.ntiid] = x

		courses_to_remove = []
		for course in my_enrollments.values():
			if ICourseSubInstance.providedBy(course):
				# Look for parents and siblings to remove
				courses_to_remove.extend( course.__parent__.values() )
				courses_to_remove.append( course.__parent__.__parent__ )
			else:
				# Look for children to remove
				courses_to_remove.extend(course.SubInstances.values())
		for course in courses_to_remove:
			ntiid = ICourseCatalogEntry(course).ntiid
			if ntiid not in my_enrollments:
				container.pop( ntiid, None )

	accepts = ()

	def __getitem__(self, key):
		"We can be traversed to the CourseCatalog."
		# Due to a mismatch between the global course catalog name
		# of 'CourseCatalog', and the local course catalog name of
		# 'Courses', we accept either
		if key == self.container.__name__ or key in ('Courses', 'CourseCatalog'):
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
			if o.__name__ == key or ICourseCatalogEntry(o).__name__ == key:
				return o

		# No actual match. Legacy ProviderUniqueID?
		for o in self.container:
			if ICourseCatalogEntry(o).ProviderUniqueID == key:
				logger.warning("Using legacy provider ID to match %s to %s", key, o)
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
		try:
			# We probably want a better value than `ntiid`? Human readable?
			# or is this supposed to be traversable?
			return ICourseCatalogEntry(self._private_course_instance).ntiid
		except TypeError: # Hmm, the catalog entry is gone, something doesn't match. What?
			logger.warning("Failed to get name from catalog for %s/%s",
						   self._private_course_instance,
						   self._private_course_instance.__name__)
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

	# Recall that this objects must be mutable and non-persistent

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


def LegacyCourseInstanceEnrollment(course_instance, user):
	record = ICourseEnrollments(course_instance).get_enrollment_for_principal(user)
	return DefaultCourseInstanceEnrollment(record, user)

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord
from nti.externalization.oids import to_external_ntiid_oid

@interface.implementer(interfaces.ILegacyCourseInstanceEnrollment)
@component.adapter(ICourseInstanceEnrollmentRecord)
class DefaultCourseInstanceEnrollment(CourseInstanceEnrollment):
	__external_class_name__ = 'CourseInstanceEnrollment'
	def __init__(self, record, user=None):
		CourseInstanceEnrollment.__init__(self, record.CourseInstance, record.Principal)
		self._record = record
		self.lastModified = self._record.lastModified
		self.createdTime = self._record.createdTime

	@property
	def ntiid(self):
		return to_external_ntiid_oid(self._record)

	@Lazy
	def LegacyEnrollmentStatus(self):
		# XXX Can do better
		if self._record.Scope == 'Public':
			return 'Open'
		return 'ForCredit'

def enrollment_from_record(course, record):
	return DefaultCourseInstanceEnrollment(record)

@interface.implementer(ICourseCatalogEntry)
def wrapper_to_catalog(wrapper):
	return ICourseCatalogEntry(wrapper.CourseInstance)

@interface.implementer(interfaces.IEnrolledCoursesCollection)
class EnrolledCoursesCollection(_AbstractQueryBasedCoursesCollection):

	#: Our name, part of our URL.
	__name__ = 'EnrolledCourses'
	name = alias('__name__',__name__)

	# TODO: Need to add an accepts for what the
	# POST-to-enroll takes. For now, just generic
	accepts = ("application/json",)

	query_interface = IPrincipalEnrollments
	query_attr = 'iter_enrollments'
	contained_interface = interfaces.ICourseInstanceEnrollment
	user_extra_auth = ACT_DELETE

@interface.implementer(interfaces.ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(SchemaConfigured,
									   _AbstractInstanceWrapper):
	createDirectFieldProperties(interfaces.ICourseInstanceAdministrativeRole,
								# Be flexible about what this is,
								# the LegacyCommunityInstance doesn't fully comply
								omit=('CourseInstance',))

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
		catalog = component.queryUtility( ICourseCatalog )
		for entry in catalog.iterCatalogEntries():
			instance = ICourseInstance(entry)
			if self.user in instance.instructors:
				roles = IPrincipalRoleMap(instance)
				role = 'teaching assistant'
				if roles.getSetting(RID_INSTRUCTOR, self.user.id) is Allow:
					role = 'instructor'
				yield CourseInstanceAdministrativeRole(RoleName=role,
													   CourseInstance=instance )
	iter_enrollments = iter_administrations # for convenience

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

from .interfaces import ICourseCatalogLegacyContentEntry

@component.adapter(ICourseCatalogLegacyContentEntry)
class CatalogEntryLocationInfo(LocationPhysicallyLocatable):
	"""
	We make catalog entries always appear relative to the
	user if a request is in progress.

	XXX: Why? We used do do this for everything, but now they have
	nice paths...backing this down to the far legacy type
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
												  IPrincipalEnrollments):
			for enrollment in enrollments.iter_enrollments():
				course = ICourseInstance(enrollment)
				for instructor in course.instructors:
					yield instructor.id

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of an Atom/OData workspace and collection for courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.container.contained import Contained

from zope.intid import IIntIds

from zope.location.traversing import LocationPhysicallyLocatable

from zope.securitypolicy.interfaces import Allow
from zope.securitypolicy.interfaces import IPrincipalRoleMap

from nti.appserver.workspaces.interfaces import IUserService
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.common.property import Lazy
from nti.common.property import alias

from nti.contenttypes.courses.index import IX_COURSE
from nti.contenttypes.courses.index import IX_USERNAME
from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.dataserver.interfaces import IUser

from nti.dataserver.authorization import ACT_DELETE
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.schema.field import SchemaConfigured
from nti.schema.fieldproperty import createDirectFieldProperties

from .interfaces import ICoursesWorkspace
from .interfaces import IUserAdministeredCourses
from .interfaces import ICourseInstanceEnrollment
from .interfaces import IEnrolledCoursesCollection
from .interfaces import IAdministeredCoursesCollection
from .interfaces import ILegacyCourseInstanceEnrollment
from .interfaces import ICourseInstanceAdministrativeRole
from .interfaces import IPrincipalAdministrativeRoleCatalog

@interface.implementer(ICoursesWorkspace)
class UserCourseWorkspace(Contained):

	# : Our name, part of our URL
	__name__ = 'Courses'
	name = alias('__name__', __name__)

	def __init__(self, user_service, catalog):
		self.catalog = catalog
		self.context = user_service
		self.user = user_service.user

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
		"""
		Make us traversable to collections.
		"""
		for i in self.collections:
			if i.__name__ == key:
				return i
		raise KeyError(key)

	def __len__(self):
		return len(self.collections)
_CoursesWorkspace = UserCourseWorkspace

@component.adapter(IUserService)
@interface.implementer(ICoursesWorkspace)
def CoursesWorkspace(user_service):
	"""
	The courses for a user reside at the path ``/users/$ME/Courses``.
	"""
	catalog = component.queryUtility(ICourseCatalog)
	if catalog is not None:
		# Ok, patch up the parent relationship
		workspace = _CoursesWorkspace(user_service, catalog)
		workspace.__parent__ = workspace.user
		return workspace

# XXX: We'd like to be able to use nti.appserver.pyramid_authorization:is_readable
# here because of all the caching it can do, but we are passing in an
# arbitrary user.

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import has_permission

from nti.externalization.interfaces import LocatedExternalDict

@interface.implementer(IContainerCollection)
class AllCoursesCollection(Contained):

	# : Our name, part of our URL.
	__name__ = 'AllCourses'

	accepts = ()
	name = alias('__name__', __name__)

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
		my_enrollments = {}
		container = self.container = self._IteratingDict()
		container.__name__ = parent.catalog.__name__
		container.__parent__ = parent.catalog.__parent__
		container.lastModified = parent.catalog.lastModified
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
				courses_to_remove.extend(course.__parent__.values())
				courses_to_remove.append(course.__parent__.__parent__)
			else:
				# Look for children to remove
				courses_to_remove.extend(course.SubInstances.values())

		for course in courses_to_remove:
			ntiid = ICourseCatalogEntry(course).ntiid
			if ntiid not in my_enrollments:
				container.pop(ntiid, None)

	def __getitem__(self, key):
		"""
		We can be traversed to the CourseCatalog.
		"""
		# Due to a mismatch between the global course catalog name
		# of 'CourseCatalog', and the local course catalog name of
		# 'Courses', we accept either
		if key == self.container.__name__ or key in ('Courses', 'CourseCatalog'):
			return self.container
		raise KeyError(key)

	def __len__(self):
		return 1

from nti.dataserver.datastructures import LastModifiedCopyingUserList

class _AbstractQueryBasedCoursesCollection(Contained):
	"""
	Performs subscription-adapter based queries to find
	the eligible objects.
	"""

	query_attr = None
	query_interface = None
	contained_interface = None

	user_extra_auth = None

	accepts = ()

	def __init__(self, parent):
		self.__parent__ = parent

	def _apply_user_extra_auth(self, enrollments):
		parent = self.__parent__
		if not self.user_extra_auth:
			return enrollments
		else:
			for enrollment in enrollments or ():
				course = ICourseInstance(enrollment)
				enrollment._user = parent.user
				enrollment.__acl__ = acl_from_aces(ace_allowing(parent.user,
																self.user_extra_auth,
																type(self)))
				enrollment.__acl__.extend((ace_allowing(i, ACT_READ, type(self))
										   for i in course.instructors))
		return enrollments

	def _build_container(self):
		parent = self.__parent__
		container = LastModifiedCopyingUserList()
		for catalog in component.subscribers((parent.user,), self.query_interface):
			queried = getattr(catalog, self.query_attr)()
			container.extend(queried)
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

		self._apply_user_extra_auth(container)
		return container

	@Lazy
	def container(self):
		result = self._build_container()
		return result

	def __getitem__(self, key):
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

class _AbstractInstanceWrapper(Contained):

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
		except TypeError:  # Hmm, the catalog entry is gone, something doesn't match. What?
			logger.warning("Failed to get name from catalog for %s/%s",
						   self._private_course_instance,
						   self._private_course_instance.__name__)
			return self._private_course_instance.__name__

	def __conform__(self, iface):
		if ICourseInstance.isOrExtends(iface):
			return self._private_course_instance

@component.adapter(ICourseInstance)
@interface.implementer(ICourseInstanceEnrollment)
class CourseInstanceEnrollment(_AbstractInstanceWrapper):
	__external_can_create__ = False

	_user = None
	Username = None

	# Recall that this objects must be mutable and non-persistent

	def __init__(self, course, user=None):
		super(CourseInstanceEnrollment, self).__init__(course)
		if user:
			self._user = user
			self.Username = user.username

	def xxx_fill_in_parent(self):
		if self._user:
			service = IUserService(self._user)
			ws = ICoursesWorkspace(service)
			enr_coll = EnrolledCoursesCollection(ws)
			self.__parent__ = enr_coll
			getattr(self, '__name__')  # ensure we have this

	def __conform__(self, iface):
		if IUser.isOrExtends(iface):
			return self._user
		return super(CourseInstanceEnrollment, self).__conform__(iface)

def LegacyCourseInstanceEnrollment(course_instance, user):
	record = ICourseEnrollments(course_instance).get_enrollment_for_principal(user)
	if record is not None:
		return DefaultCourseInstanceEnrollment(record, user)

from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.externalization.oids import to_external_ntiid_oid

@component.adapter(ICourseInstanceEnrollmentRecord)
@interface.implementer(ILegacyCourseInstanceEnrollment)
class DefaultCourseInstanceEnrollment(CourseInstanceEnrollment):

	__external_class_name__ = 'CourseInstanceEnrollment'

	def __init__(self, record, user=None):
		CourseInstanceEnrollment.__init__(self, record.CourseInstance, record.Principal)
		self._record = record
		self.createdTime = self._record.createdTime
		self.lastModified = self._record.lastModified

	@property
	def ntiid(self):
		return to_external_ntiid_oid(self._record)

	@Lazy
	def LegacyEnrollmentStatus(self):
		# CS/JZ/JAM: For legacy purposes we need to always return either Open or ForCredit
		# See interface ILegacyCourseInstanceEnrollment
		scope = self._record.Scope
		if scope in (ES_CREDIT, ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE):
			return ES_CREDIT
		return 'Open'

	@Lazy
	def RealEnrollmentStatus(self):
		# CS: For display use the real scope
		return self._record.Scope

def enrollment_from_record(course, record):
	return DefaultCourseInstanceEnrollment(record)

@interface.implementer(ICourseCatalogEntry)
def wrapper_to_catalog(wrapper):
	return ICourseCatalogEntry(wrapper.CourseInstance)

@interface.implementer(IEnrolledCoursesCollection)
class EnrolledCoursesCollection(_AbstractQueryBasedCoursesCollection):

	# : Our name, part of our URL.
	__name__ = 'EnrolledCourses'
	name = alias('__name__', __name__)

	# TODO: Need to add an accepts for what the
	# POST-to-enroll takes. For now, just generic
	accepts = ("application/json",)

	query_attr = 'iter_enrollments'
	query_interface = IPrincipalEnrollments
	contained_interface = ICourseInstanceEnrollment

	user_extra_auth = ACT_DELETE

	def _build_from_catalog(self):
		user = self.__parent__.user
		intids = component.getUtility(IIntIds)
		catalog = component.getUtility(ICourseCatalog)
		courses = [x.ntiid for x in catalog.iterCatalogEntries()]

		catalog = get_enrollment_catalog()
		result = LastModifiedCopyingUserList()
		query = {IX_COURSE:{'any_of':courses}, IX_USERNAME:{'any_of':(user.username,)}}
		for uid in catalog.apply(query) or ():
			context = intids.queryObject(uid)
			if ICourseInstanceEnrollmentRecord.providedBy(context):
				result.append(self.contained_interface(context))

		self._apply_user_extra_auth(result)
		return result

# administered courses

@interface.implementer(ICourseInstanceAdministrativeRole)
class CourseInstanceAdministrativeRole(SchemaConfigured,
									   _AbstractInstanceWrapper):
	createDirectFieldProperties(ICourseInstanceAdministrativeRole,
								# Be flexible about what this is,
								# the LegacyCommunityInstance doesn't fully comply
								omit=('CourseInstance',))

	def __init__(self, CourseInstance=None, RoleName=None):
		# SchemaConfigured is not cooperative
		SchemaConfigured.__init__(self, RoleName=RoleName)
		_AbstractInstanceWrapper.__init__(self, CourseInstance)

@component.adapter(IUser)
@interface.implementer(IPrincipalAdministrativeRoleCatalog)
class _DefaultPrincipalAdministrativeRoleCatalog(object):
	"""
	This catalog checks all courses the user is in the instructors list.
	"""

	def __init__(self, user):
		self.user = user

	def _iter_admin_courses(self):
		util = component.getUtility(IUserAdministeredCourses)
		for context in util.iter_admin(self.user):
			yield context

	def iter_administrations(self):
		for course in self._iter_admin_courses():
			roles = IPrincipalRoleMap(course)
			role = 'teaching assistant'
			if roles.getSetting(RID_INSTRUCTOR, self.user.id) is Allow:
				role = 'instructor'
			yield CourseInstanceAdministrativeRole(RoleName=role, CourseInstance=course)
	iter_enrollments = iter_administrations  # for convenience

	def count_administrations(self):
		result = list(self._iter_admin_courses())
		return len(result)

	count_enrollments = count_administrations

@interface.implementer(IAdministeredCoursesCollection)
class AdministeredCoursesCollection(_AbstractQueryBasedCoursesCollection):

	# : Our name, part of our URL.
	__name__ = 'AdministeredCourses'
	name = alias('__name__', __name__)

	query_attr = 'iter_administrations'
	query_interface = IPrincipalAdministrativeRoleCatalog
	contained_interface = ICourseInstanceAdministrativeRole

from zope.location.interfaces import IRoot
from zope.location.interfaces import ILocationInfo

from pyramid.threadlocal import get_current_request

from nti.dataserver.users import User
from nti.dataserver.interfaces import IDataserver

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
			user = User.get_user(userid, dataserver=ds)
			service = IUserService(user)
			workspace = CoursesWorkspace(service)
			all_courses = AllCoursesCollection(workspace)

			parents.append(all_courses)
			parents.append(workspace)
			parents.append(user)
			parents.extend(ILocationInfo(user).getParents())

		else:
			parents.append(ds.dataserver_folder)
			parents.extend(ILocationInfo(ds.dataserver_folder).getParents())

		if not IRoot.providedBy(parents[-1]):
			raise TypeError("Not enough context to get all parents")
		return parents

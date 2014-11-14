#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrated courseware-related interfaces. This
is a high-level package built mostly upon the low-level
datastructures defined in :mod:`nti.app.products.courses`.

.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

# disable missing self
# pylint:disable=I0011,E0213,E0211

from zope import interface
from zope.security.permission import Permission
from zope.container.interfaces import IContained
from zope.interface.common.mapping import IEnumerableMapping

from nti.appserver.interfaces import IWorkspace
from nti.appserver.interfaces import IContainerCollection

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.dataserver.interfaces import ILastModified
from nti.dataserver.interfaces import IShouldHaveTraversablePath

from nti.ntiids.schema import ValidNTIID

from nti.schema.field import Bool
from nti.schema.field import Dict
from nti.schema.field import Choice
from nti.schema.field import Object
from nti.schema.field import ValidTextLine as TextLine

import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecatedFrom(
	"Moved to nti.contenttypes.courses",
	"nti.contenttypes.courses.interfaces",
	"ICourseCatalogEntry",
	"ICourseCatalogInstructorInfo",
	"ICourseInstanceAvailableEvent",
	"CourseInstanceAvailableEventg")
zope.deferredimport.deprecatedFrom(
	"Moved to nti.contenttypes.courses",
	"nti.contenttypes.courses.legacy_catalog",
	"ICourseCatalogInstructorLegacyInfo",
	"ICourseCreditLegacyInfo",
	'ICourseCatalogLegacyEntry')

zope.deferredimport.deprecated(
	"Moved to nti.contenttypes.courses",
	# XXX: Note the aliasing: This is somewhat dangerous if we
	# attempt to register things by this interface!
	ICourseCatalog="nti.contenttypes.courses.interfaces:IWritableCourseCatalog")


ACT_VIEW_ROSTER = Permission('nti.actions.courseware.view_roster')
ACT_VIEW_ACTIVITY = Permission('nti.actions.courseware.view_activity')

from nti.contenttypes.courses.legacy_catalog import ICourseCatalogLegacyEntry as _ICourseCatalogLegacyEntry

class ICourseCatalogLegacyContentEntry(_ICourseCatalogLegacyEntry):
	ContentPackageNTIID = ValidNTIID(title="The NTIID of the root content package")

class ILegacyCommunityBasedCourseInstance(ICourseInstance):
	"""
	Marker interface for a legacy course instance
	"""

	LegacyScopes = Dict(title="'public' and 'restricted' entity ids",
						readonly=True)

	ContentPackageBundle = interface.Attribute("A mock bundle, having a ContentPackages iterable")

class ICourseInstanceActivity(IContained, ILastModified):
	"""
	A firehose implementation of activity relating
	to a course and typically expected to be visible to
	instructors/administrators of the course.

	An implementation of this interface will be available
	by adapting a course to it.
	"""

	def __len__():
		"How many items are in this collection."

	def append(activity):
		"""
		Note that the ``activity`` relevant to this course
		has happened. The ``activity`` object must have an intid,
		and it will be stored along with an approximate timestamp
		of when it occurred. Note that if activity is happening on multiple
		machines, relative times will only be as good as clock
		synchronization.
		"""

	def remove(activity):
		"""
		Remove the activity from the list for this course.
		Note that this may be very expensive.
		"""

	def items(min=None,max=None,excludemin=False,excludemax=False):
		"""
		Return an iterator over the activity items stored for this
		course. The iterator is returned in sorted order, with
		most recent items first.

		:keyword min: If given, a timestamp.
		:keyword max: If given, a timestamp.
		"""

class ICoursesWorkspace(IWorkspace):
	"""
	A workspace containing data for courses.
	"""

class IEnrolledCoursesCollection(IContainerCollection):
	"""
	A collection (local to a user) of courses he is enrolled in
	(:class:`.ICourseInstanceEnrollment`)
	"""

class ICourseInstanceEnrollment(IShouldHaveTraversablePath):
	"""
	An object representing a principal's enrollment in a course
	instance.

	Implementations should be adaptable to their course instance
	and the corresponding catalog entry.

	These objects should be non-persistent and derived from the
	underlying :class:`.ICourseInstanceEnrollmentRecord`, but
	independently mutable.
	"""

	__name__ = interface.Attribute("The name of the enrollment is the same as the CourseInstance.")

	CourseInstance = Object(ICourseInstance)

	Username = TextLine(title="The user this is about",
							   required=False,
							   readonly=True)

class ILegacyCourseInstanceEnrollment(ICourseInstanceEnrollment):
	"""
	An object with information about enrollment in a legacy course.
	"""

	LegacyEnrollmentStatus = TextLine(title="The type of enrollment, ForCredit or Open",
									  required=True,
									  readonly=True,
									  default='Open')
	
	RealEnrollmentStatus = TextLine(title="The type of enrollment (Scope)",
									required=False,
									readonly=True)

class IPrincipalEnrollmentCatalog(IPrincipalEnrollments):
	"""
	Extends the base enrollments interface to be in terms
	of the :class:`.ICourseInstanceEnrollment` objects defined
	in this module.

	There can be multiple catalogs of enrollments for courses
	that are managed in different ways. Therefore, commonly
	implementations will be registered as subscription adapters
	from the user.
	"""

	def iter_enrollments():
		"""
		Iterate across :class:`.ICourseInstanceEnrollment` objects, or at
		least something that can be adapted to that interface.
		(Commonly, this will return actual :class:`.ICourseInstance`
		objects; we provide an adapter from that to the enrollment.)
		"""

class ICourseInstanceAdministrativeRole(IShouldHaveTraversablePath):
	"""
	An object representing a principal's administrative
	role within a course instance.

	Currently, the only supported role is that of instructor, and that
	role is static; thus, this object cannot be deleted or altered
	externally.) In the future as there are more roles (such as TA)
	and those roles are made dynamic, instances of this
	object may be able to be DELETEd or POSTd.

	Implementations should be adaptable to their course instance
	and the corresponding catalog entry.
	"""

	__name__ = interface.Attribute("The name of the administration is the same as the CourseInstance.")

	RoleName = Choice(title="The name of the role this principal holds",
					  values=('instructor','teaching assistant'))
	CourseInstance = Object(ICourseInstance)

class IPrincipalAdministrativeRoleCatalog(interface.Interface):
	"""
	Something that can provide information about all courses
	administered by the principal.

	There can be multiple catalogs for courses that are managed in
	different ways. Therefore, commonly implementations will be
	registered as subscription adapters from the user.
	"""

	def iter_administrations():
		"""
		Iterate across :class:`.ICourseInstanceAdministrativeRole` objects, or at
		least something that can be adapted to that interface.
		"""

class IAdministeredCoursesCollection(IContainerCollection):
	"""
	A collection (local to a user) of courses he administers
	(:class:`.ICourseInstanceAdministrativeRole`)
	"""

from nti.contentlibrary.interfaces import ILegacyCourseConflatedContentPackage

class ILegacyCourseConflatedContentPackageUsedAsCourse(ILegacyCourseConflatedContentPackage):
	"""
	A marker applied on top of a content package that was already
	conflated when it is actually being used by a course.

	Remember that this can only happen in the global library with non-persistent
	content packages; the code in :mod:`legacy_catalog` will refuse to turn
	any persistent content package in a site library into a course. Therefore this
	marker interface can be used to distinguish things that are actually being
	used as :class:`ILegacyCommunityBasedCourseInstance` and which are not.

	When this marker is applied, instances should get access to
	an attribute ``_v_global_legacy_catalog_entry`` that points to the catalog
	entry, which should also be global and not persistent. Access this attribute
	to get the catalog entry; yes, it will lead to warnings in your code about
	a private attribute, but it will be easy to clean them up later, and we want
	this ugliness to stand out.
	"""

#: A preliminary special type of NTIID that refers to an abstract
#: notion of a topic within a particular abstract course. When
#: resolved, we will find the specific course (sub)instance the user is
#: enrolled in and return the closest matching topic. This type of
#: NTIID is semi-suitable for use in content and other long-lived places.
#:
#: The `provider` field should be the value of the `ProviderUniqueID`
#: from the course catalog for the top-level course (not section/subinstance).
NTIID_TYPE_COURSE_SECTION_TOPIC = 'Topic:EnrolledCourseSection'

#: Similar to :const:`.NTIID_TYPE_COURSE_SECTION_TOPIC`, but instead
#: returns the top-level course topic, never the course topic
#: for a subsection.
NTIID_TYPE_COURSE_TOPIC = 'Topic:EnrolledCourseRoot'

class IEnrollmentOption(IContained):
	"""
	Marker interface for a course/entry enrollment option
	"""
	
	Name = TextLine(title="Enrollment option name", required=True)
	Name.setTaggedValue('_ext_excluded_out', True)
	
	CatalogEntryNTIID = TextLine(title="Catalog entry NTIID", required=False)
	CatalogEntryNTIID.setTaggedValue('_ext_excluded_out', True)
	
class IOpenEnrollmentOption(IEnrollmentOption):
	
	"""
	Open course/entry enrollment option
	"""

	Enabled = Bool(title="If the course allows open enrollemnt", 
				   required=False, default=True)

class IEnrollmentOptions(IEnumerableMapping):
	
	"""
	Marker interface for an object that hold :class:`.IEnrollmentOption` objects
	for a course.
	"""
	
	def append(option):
		"""
		add an enrollment option
		"""

class IEnrollmentOptionProvider(interface.Interface):
	
	"""
	subscriber for a course/entry enrollment options
	"""
	
	def iter_options():
		"""
		return a iterable of :class:`.IEnrollmentOption` for the specified course
		"""

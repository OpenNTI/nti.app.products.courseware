#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrated courseware-related interfaces. This
is a high-level package built mostly upon the low-level
datastructures defined in :mod:`nti.app.products.courses`.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.location.interfaces import ILocation
from zope.container.interfaces import IContained

from nti.appserver import interfaces as app_interfaces
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.interfaces import IShouldHaveTraversablePath
from nti.dataserver.interfaces import ILastModified

from nti.utils import schema
from nti.ntiids.schema import ValidNTIID

class ICourseCatalog(interface.Interface):
	"""
	Something that manages the set of courses
	available in the system and provides
	ways to query for courses and find
	out information about them.
	"""

	# TODO: What is this a specialization of, anything?

class ICourseCatalogInstructorInfo(interface.Interface):
	"""
	Information about a course instructor.

	.. note:: Almost all of this could/should
		come from a user profile. That way the user
		can be in charge of it. Pictures would come from
		the user's avatar URL.
	"""

	Name = schema.TextLine(title="The instructor's name")
	Title = schema.TextLine(title="The instructor's title of address such as Dr.",
							required=False)
	JobTitle = schema.TextLine(title="The instructor's academic job title")
	Suffix = schema.TextLine(title="The instructor's suffix such as PhD or Jr",
							 required=False)

class ICourseCatalogInstructorLegacyInfo(ICourseCatalogInstructorInfo):
	"""
	Additional legacy info about course instructors.
	"""

	defaultphoto = schema.DataURI(title="An extra copy of the instructor's photo",
								  required=False)

	username = schema.TextLine(title="A username string that may or may not refer to an actual account.",
							   required=False)
	username.setTaggedValue('_ext_excluded_out', True) # Internal use only

class ICourseCreditLegacyInfo(interface.Interface):
	"""
	Describes how academic credit can be obtained
	for this course.

	"""

	Hours = schema.Int(title="The number of hours that can be earned.",
					   min=1)
	Enrollment = schema.Dict(title="Information about how to enroll. This is not modeled.",
							 key_type=schema.TextLine(title="A key"),
							 value_type=schema.TextLine(title="A value"))

class ICourseCatalogEntry(ILocation):
	"""
	An entry in the course catalog containing metadata
	and presentation data about the course.

	Much of this is poorly modeled and a conglomeration of things
	found in several previous places.

	In general, these objects should be adaptable to their
	corresponding :class:`.ICourseInstance`, and the
	course instance should be adaptable back to its corresponding
	entry.
	"""

	Title = schema.TextLine(title="The provider's descriptive title")
	Description = schema.Text(title="The provider's paragraph-length description")

	StartDate = schema.Date(title="The date on which the course begins",
							description="Currently optional; a missing value means the course already started")
	Duration = schema.Timedelta(title="The length of the course",
								description="Currently optional, may be None")
	EndDate = schema.Date( title="The date on which the course ends",
						   description="Currently optional; a missing value means the course has no defined end date.")


	ProviderUniqueID = schema.TextLine(title="The unique id assigned by the provider")
	ProviderDepartmentTitle = schema.TextLine(title="The string assigned to the provider's department offering the course")

	Instructors = schema.ListOrTuple(title="The instuctors. Order might matter",
									 value_type=schema.Object(ICourseCatalogInstructorInfo) )

class ICourseCatalogLegacyEntry(ICourseCatalogEntry):
	"""
	Adds information used by or provided from legacy sources.
	"""

	# Legacy, will go away given a more full description of the
	# course.
	ContentPackageNTIID = ValidNTIID(title="The NTIID of the root content package")

	# Legacy. This isn't really part of the course catalog.
	Communities = schema.ListOrTuple(value_type=schema.TextLine(title='The community'),
									 title="Course communities",
									 required=False)

	# While this might be a valid part of the course catalog, this
	# representation of it isn't very informative or flexible
	Credit = schema.List(value_type=schema.Object(ICourseCreditLegacyInfo),
						 title="Either missing or an array with one entry.",
						 required=False)

	Video = schema.ValidURI(title="A URL-like string, possibly using private-but-un-prefixed schemes, or the empty string or missing.",
							required=False)

	Schedule = schema.Dict(title="An unmodeled dictionary, possibly useful for presentation.")

	Prerequisites = schema.List(title="A list of dictionaries suitable for presentation. Expect a `title` key.",
								value_type=schema.Dict(key_type=schema.TextLine(),
													   value_type=schema.TextLine()))

	### These are being replaced with presentation specific asset bundles
	# (one path is insufficient to handle things like retina displays
	# and the various platforms).
	LegacyPurchasableIcon = schema.TextLine(title="A URL or path of indeterminate type or meaning",
											required=False)

	LegacyPurchasableThumbnail = schema.TextLine(title="A URL or path of indeterminate type or meaning",
												 required=False)


class ILegacyCommunityBasedCourseInstance(ICourseInstance):
	"""
	Marker interface for a legacy course instance
	"""

	LegacyScopes = schema.Dict(title="'public' and 'restricted' entity ids",
							   readonly=True)
	LegacyInstructorForums = schema.ValidTextLine(title='A space separated list of forum NTIIDs',
												  readonly=True)

class ICourseInstanceActivity(IContained,ILastModified):
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

from zope.interface.interfaces import IObjectEvent
from zope.interface.interfaces import ObjectEvent

class ICourseInstanceAvailableEvent(IObjectEvent):
	"""
	An event that is sent, usually during startup, to notify that a
	course instance has been setup by this package. This is a hook for
	additional packages to perform any setup they need to do,
	such as synchronizing database state with course content state.
	"""

@interface.implementer(ICourseInstanceAvailableEvent)
class CourseInstanceAvailableEvent(ObjectEvent):
	pass



class ICoursesWorkspace(app_interfaces.IWorkspace):
	"""
	A workspace containing data for courses.
	"""

class IEnrolledCoursesCollection(app_interfaces.IContainerCollection):
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
	"""

	__name__ = interface.Attribute("The name of the enrollment is the same as the CourseInstance.")

	CourseInstance = schema.Object(ICourseInstance)

	Username = schema.TextLine(title="The user this is about",
							   required=False,
							   readonly=True)

class ILegacyCourseInstanceEnrollment(ICourseInstanceEnrollment):
	"""
	An object with information about enrollment in a legacy course.
	"""

	LegacyEnrollmentStatus = schema.TextLine(title="The type of enrollment, ForCredit or Open",
											 required=True,
											 readonly=True,
											 default='Open')

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

	RoleName = schema.Choice(title="The name of the role this principal holds",
							 values=('instructor',))
	CourseInstance = schema.Object(ICourseInstance)

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
class IAdministeredCoursesCollection(app_interfaces.IContainerCollection):
	"""
	A collection (local to a user) of courses he is enrolled in
	(:class:`.ICourseInstanceAdministrativeRole`)
	"""

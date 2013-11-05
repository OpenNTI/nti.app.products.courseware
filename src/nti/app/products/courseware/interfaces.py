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
from nti.appserver import interfaces as app_interfaces
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

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
	"""
	# TODO: Almost all of this could/should
	# come from a user profile. That way the user
	# can be in charge of it. Pictures would come from
	# the user's avatar URL.

	Name = schema.TextLine(title="The instructor's name")
	Title = schema.TextLine(title="The instructor's title of address such as Dr.",
							required=False)
	JobTitle = schema.TextLine(title="The instructor's academic job title")
	Suffix = schema.TextLine(title="The instructor's suffix such as PhD or Jr",
							 required=False)

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
	"""

	Title = schema.TextLine(title="The provider's descriptive title")
	Description = schema.Text(title="The provider's paragraph-length description")

	StartDate = schema.Date(title="The date on which the course begins",
							description="Currently optional; a missing value means the course already started")
	Duration = schema.Timedelta(title="The length of the course",
								description="Currently optional")


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

class ICoursesWorkspace(app_interfaces.IWorkspace):
	"""
	A workspace containing data for courses.
	"""

class IPrincipalEnrollmentCatalog(IPrincipalEnrollments):
	"""
	Extends the base enrollments interface to be in terms
	of the :class:`.ICourseCatalogEntry` objects defined
	in this module.
	"""

	def iter_enrollments():
		"Iterate across :class:`.ICourseCatalogEntry` objects. "

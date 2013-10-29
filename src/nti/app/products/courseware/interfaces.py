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

from nti.utils import schema
from zope.configuration import fields
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

class ICourseCatalogEntry(interface.Interface):
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

	# Legacy, will go away given a more full description of the
	# course.
	ContentPackageNTIID = ValidNTIID(title="The NTIID of the root content package")

	# Legacy. This isn't really part of the course catalog.
	Communities = schema.ListOrTuple(value_type=schema.TextLine(title='The community'),
									 title="Course communities",
									 required=False)

	ProviderUniqueID = schema.TextLine(title="The unique id assigned by the provider")
	ProviderDepartmentTitle = schema.TextLine(title="The string assigned to the provider's department offering the course")

	Instructors = schema.ListOrTuple(title="The instuctors. Order might matter",
									 value_type=schema.Object(ICourseCatalogInstructorInfo) )

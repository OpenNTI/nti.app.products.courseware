#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for integrating with legacy course catalog information.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

import simplejson as json
import isodate
import datetime
import pytz
import os

from zope.cachedescriptors.property import readproperty

from nti.contentlibrary import interfaces as lib_interfaces
from zope.lifecycleevent import IObjectAddedEvent

from nti.utils.schema import PermissiveSchemaConfigured as SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from urlparse import urljoin

from nti.externalization.externalization import to_external_object

from .catalog import CourseCatalogInstructorInfo
from .catalog import CourseCatalogEntry
from . import interfaces

@interface.implementer(interfaces.ICourseCreditLegacyInfo)
class CourseCreditLegacyInfo(SchemaConfigured):
	createDirectFieldProperties(interfaces.ICourseCreditLegacyInfo)

@interface.implementer(interfaces.ICourseCatalogLegacyEntry)
class CourseCatalogLegacyEntry(CourseCatalogEntry):
	createDirectFieldProperties(interfaces.ICourseCatalogLegacyEntry)

	#: For legacy catalog entries created from a content package,
	#: this will be that package (an implementation of
	#: :class:`.ILegacyCourseConflatedContentPackage`)
	legacy_content_package = None

	@property
	def EndDate(self):
		"""
		We calculate the end date based on the duration and the start
		date, if possible. Otherwise, None.
		"""
		if self.StartDate is not None and self.Duration is not None:
			return self.StartDate + self.Duration

	@readproperty
	def Preview(self):
		"""
		If a preview hasn't been specifically set, we derive it
		if possible.
		"""
		if self.StartDate is not None:
			return self.StartDate > datetime.datetime.utcnow()


	@property
	def __acl__(self):
		"we have no opinion on acls"
		return ()

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.dataserver.interfaces import IPrincipal
from nti.dataserver.users import Entity

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization import ACT_READ

class CourseCatalogLegacyNonPublicEntry(CourseCatalogLegacyEntry):
	"""
	This entry has an ACL that provides access only to those people that
	are 'enrolled' in the course according to the 'restricted' legacy scrope.
	"""

	__external_class_name__ = 'CourseCatalogLegacyEntry'
	__external_can_create__ = False

	@readproperty
	def __acl__(self):
		course = ICourseInstance(self, None)
		if course is None: # No course instance yet, which is where the scopes are.
			return [ACE_DENY_ALL]

		restricted_id = course.LegacyScopes['restricted']
		restricted = Entity.get_entity(restricted_id) if restricted_id else None

		if restricted is None: # No community yet
			acl= [ACE_DENY_ALL]
		else:
			acl = acl_from_aces(
				ace_allowing( IPrincipal(restricted), ACT_READ, CourseCatalogLegacyNonPublicEntry )
				)
			acl.extend( (ace_allowing( i, ACT_READ, CourseCatalogLegacyNonPublicEntry)
						 for i in course.instructors) )
			acl.append( ACE_DENY_ALL )
		self.__acl__ = acl # cache
		return acl


	def HACK_make_acl(self):
		return self.__acl__


@interface.implementer(interfaces.ICourseCatalogInstructorLegacyInfo)
class CourseCatalogInstructorLegacyInfo(CourseCatalogInstructorInfo):
	defaultphoto = None
	createDirectFieldProperties(interfaces.ICourseCatalogInstructorLegacyInfo)

@component.adapter(lib_interfaces.ILegacyCourseConflatedContentPackage, IObjectAddedEvent)
def _content_package_registered( package, event ):
	# There are currently two types of renderings in the wild:
	# Those with and without a 'course-info.json' file. Those
	# without a JSON file have some extra info in their TOC.
	# Unfortunately, *neither one* of those renderings
	# has a complete set of information. The old legacy 'purchasables'
	# also contains information, which is also a partially-overlapping
	# set of the information contained. Sigh.
	# Info				CourseInfo		OldTOC				Purchasable
	# ContentNTIID		N				Y					Y (items)
	# Description		Y				N					Y
	# Department		Y (school)		N					Y
	# ID				Y				Y (courseName)		Y (name)
	# Title				Y				Y (label)			Y
	# Preview			N				N					Y
	# Featured			N				N					Y
	# Instructors		Y				N					Y (author,freeform text)
	# --> This is structured data in CourseInfo, incl photo and username,
	#     realname and jobtitle
	# Communities		N				Y (scope,many)		Y
	# Big Icon			N (toc)			N (diff)			Y (used "promo")
	# --> This is used in the main Library view
	# Thumbnail			N (toc)			N					Y (not used)
	# Background		N (toc)			Y					N
	# Icon				N				Y (icon)			N (diff)
	# --> This is used in the hover menu for enrolled students
	# StartDate			Y (opt)			N					Y
	# Duration			Y (opt)			N					N
	# Schedule			Y (opt)			N					N
	# Email Sig			N				N					Y
	# Credit/Enroll		Y (opt)			N					N
	# Promo Video		Y (opt)			N					N
	# Prereqs			Y				N					N

	# Everything in the course-info.json is also copied statically to a
	# data file used to render the landing page.

	# Older course info renderings are missing some of the optional
	# elements.

	# For packages with a course-info.json, almost everything needed to
	# construct a purchasable can come from the courseinfo
	# or the ToC or convention (Big Icon) or be derived
	# (Preview and email sig).
	# The only thing missing is the 'featured' flag.

	# Things we add to the course info json file:
	# Name            Type     Default   Description
	# is_non_public   bool     False     Only (OU) enrolled students can see it; no one else can join it

	if not package.courseInfoSrc:
		logger.debug("No course info for %s", package )
		return
	info_json_string = package.read_contents_of_sibling_entry( package.courseInfoSrc )
	if not info_json_string:
		logger.warn("The package at %s claims to be a course but has no file at %s",
					package, package.courseInfoSrc )
		return
	info_json_key = package.make_sibling_key( package.courseInfoSrc )
	# Ensure we get unicode values for strings (simplejson would return bytestrings
	# if they are ASCII encodable)
	info_json_string = unicode(info_json_string, 'utf-8')
	info_json_dict = json.loads( info_json_string )

	factory = CourseCatalogLegacyEntry
	if info_json_dict.get('is_non_public'):
		factory = CourseCatalogLegacyNonPublicEntry

	catalog_entry = factory()
	if lib_interfaces.IFilesystemKey.providedBy( info_json_key ):
		catalog_entry.lastModified = os.stat(info_json_key.absolute_path).st_mtime
	else:
		raise ValueError("Unsupported key", info_json_key )

	catalog_entry.Description = info_json_dict['description']
	catalog_entry.ContentPackageNTIID = package.ntiid
	catalog_entry.Title = info_json_dict['title']
	catalog_entry.ProviderUniqueID = info_json_dict['id']
	catalog_entry.ProviderDepartmentTitle = info_json_dict['school']
	catalog_entry.Term = info_json_dict.get('term', '')
	catalog_entry.Badges = info_json_dict.get('badges', {})

	if 'startDate' in info_json_dict:
		catalog_entry.StartDate = isodate.parse_datetime(info_json_dict['startDate'])
		# Convert to UTC if needed
		if catalog_entry.StartDate.tzinfo is not None:
			catalog_entry.StartDate = catalog_entry.StartDate.astimezone(pytz.UTC).replace(tzinfo=None)
	if 'duration' in info_json_dict:
		# We have durations as strings like "16 weeks"
		duration_number, duration_kind = info_json_dict['duration'].split()
		# Turn those into keywords for timedelta.
		catalog_entry.Duration = datetime.timedelta(**{duration_kind.lower():int(duration_number)})
		# Ensure the end date is derived properly
		assert catalog_entry.StartDate is None or catalog_entry.EndDate

	# derive preview information if not provided.
	if 'isPreview' in info_json_dict:
		catalog_entry.Preview = info_json_dict['isPreview']
	else:
		if catalog_entry.StartDate and datetime.datetime.utcnow() < catalog_entry.StartDate:
			assert catalog_entry.Preview

	# For the convenience of others
	catalog_entry.legacy_content_package = package

	instructors = []
	# For externalizing the photo URLs, we need
	# to make them absolute, and we do that by making
	# the package absolute
	ext_package_href = to_external_object( package )['href']

	for inst in info_json_dict['instructors']:
		instructor = CourseCatalogInstructorLegacyInfo( Name=inst['name'],
														JobTitle=inst['title'],
														username=inst.get('username',''))
		if inst.get('defaultphoto'):
			photo_name = inst['defaultphoto']
			photo_data = package.read_contents_of_sibling_entry( photo_name )
			if photo_data:
				# Ensure it exists and is readable before we advertise it
				instructor.defaultphoto = urljoin(ext_package_href, photo_name)

		instructors.append( instructor )

	catalog_entry.Instructors = instructors

	catalog_entry.Communities = [unicode(x, 'utf-8')
								 for x in package._v_toc_node.xpath('//course/scope[@type="public"]/entry/text()')]

	if info_json_dict.get('video'):
		catalog_entry.Video = info_json_dict.get('video').encode('utf-8')
	catalog_entry.Credit = [CourseCreditLegacyInfo(Hours=d['hours'],Enrollment=d['enrollment'])
							for d in info_json_dict.get('credit', [])]
	catalog_entry.Schedule = info_json_dict.get('schedule', {})
	catalog_entry.Prerequisites = info_json_dict.get('prerequisites', [])

	catalog = component.getUtility(interfaces.ICourseCatalog)
	try:
		catalog.addCatalogEntry( catalog_entry )
	except ValueError:
		# XXX Test cases move catalog entries around
		# to deal better with sites. Fix them, then remove this.
		logger.exception("This should only happen in test cases")
		catalog.removeCatalogEntry( catalog_entry, event=False )
		catalog.addCatalogEntry(catalog_entry)

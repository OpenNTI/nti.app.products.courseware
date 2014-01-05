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
import os

from nti.contentlibrary import interfaces as lib_interfaces
from zope.lifecycleevent import IObjectAddedEvent

from nti.utils.schema import PermissiveSchemaConfigured as SchemaConfigured
from nti.utils.schema import createDirectFieldProperties
from nti.utils import dataurl

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

	if not package.courseInfoSrc:
		logger.debug("No course info for %s", package )
		return
	info_json_string = package.read_contents_of_sibling_entry( package.courseInfoSrc )
	info_json_key = package.make_sibling_key( package.courseInfoSrc )
	# Ensure we get unicode values for strings (simplejson would return bytestrings
	# if they are ASCII encodable)
	info_json_string = unicode(info_json_string, 'utf-8')
	info_json_dict = json.loads( info_json_string )

	catalog_entry = CourseCatalogLegacyEntry()
	if lib_interfaces.IFilesystemKey.providedBy( info_json_key ):
		catalog_entry.lastModified = os.stat(info_json_key.absolute_path).st_mtime
	else:
		raise ValueError("Unsupported key", info_json_key )
	catalog_entry.Description = info_json_dict['description']
	catalog_entry.ContentPackageNTIID = package.ntiid
	catalog_entry.Title = info_json_dict['title']
	catalog_entry.ProviderUniqueID = info_json_dict['id']
	catalog_entry.ProviderDepartmentTitle = info_json_dict['school']
	if 'startDate' in info_json_dict:
		catalog_entry.StartDate = isodate.parse_date(info_json_dict['startDate'])
	if 'duration' in info_json_dict:
		# We have durations as strings like "16 weeks"
		duration_number, duration_kind = info_json_dict['duration'].split()
		# Turn those into keywords for timedelta.
		catalog_entry.Duration = datetime.timedelta(**{duration_kind.lower():int(duration_number)})

	# For the convenience of others
	catalog_entry.legacy_content_package = package

	instructors = []
	for inst in info_json_dict['instructors']:
		instructor = CourseCatalogInstructorLegacyInfo( Name=inst['name'],
														JobTitle=inst['title'],
														username=inst.get('username'))
		if inst.get('defaultphoto'):
			photo_name = inst['defaultphoto']
			photo = package.read_contents_of_sibling_entry( photo_name )
			instructor.defaultphoto = dataurl.encode(photo, mime_type=b'image/png' if photo_name.endswith('.png') else b'image/jpeg' )
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

	component.getUtility(interfaces.ICourseCatalog).addCatalogEntry( catalog_entry )

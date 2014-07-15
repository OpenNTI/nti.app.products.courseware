#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for integrating with legacy course catalog information.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.contentlibrary import interfaces as lib_interfaces
from zope.lifecycleevent import IObjectAddedEvent

from nti.externalization.externalization import to_external_object
from nti.contenttypes.courses.legacy_catalog import CourseCatalogLegacyEntry
from .interfaces import ICourseCatalogLegacyContentEntry

@interface.implementer(ICourseCatalogLegacyContentEntry)
class CourseCatalogLegacyContentEntry(CourseCatalogLegacyEntry):
	__external_class_name__ = 'CourseCatalogLegacyEntry'

	ContentPackageNTIID = None
	Communities = () # Unused externally, deprecated internally
	Term = ''
	legacy_content_package = None

	@property
	def PlatformPresentationResources(self):
		try:
			return self.legacy_content_package.PlatformPresentationResources
		except AttributeError:
			return super(CourseCatalogLegacyContentEntry,self).PlatformPresentationResources

from nti.contenttypes.courses._catalog_entry_parser import fill_entry_from_legacy_key
from nti.contenttypes.courses.interfaces import ICourseCatalog


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

	info_json_key = package.make_sibling_key(package.courseInfoSrc)
	catalog_entry = CourseCatalogLegacyContentEntry()

	# For externalizing the photo URLs, we need
	# to make them absolute, and we do that by making
	# the package absolute
	ext_package_href = to_external_object( package )['href']

	fill_entry_from_legacy_key(catalog_entry, info_json_key, base_href=ext_package_href)

	# XXX still have to do this (need a decorator to actually output)
	catalog_entry.ContentPackageNTIID = package.ntiid

	# For the convenience of others
	# XXX: still have to do this?
	catalog_entry.legacy_content_package = package
	catalog_entry.Communities = [unicode(x, 'utf-8')
								 for x in package._v_toc_node.xpath('//course/scope[@type="public"]/entry/text()')]

	catalog = component.getUtility(ICourseCatalog)

	try:
		catalog.addCatalogEntry( catalog_entry )
	except ValueError:
		# XXX Test cases move catalog entries around
		# to deal better with sites. Fix them, then remove this.
		logger.exception("This should only happen in test cases")
		catalog.removeCatalogEntry( catalog_entry, event=False )
		catalog.addCatalogEntry(catalog_entry)

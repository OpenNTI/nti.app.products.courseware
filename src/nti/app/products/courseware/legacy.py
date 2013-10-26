#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Support for integrating with legacy course catalog information.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

import anyjson as json

from nti.contentlibrary import interfaces as lib_interfaces
from zope.lifecycleevent import IObjectAddedEvent

_last_json_dict = None

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
	#     realname and title
	# Communities		N				Y (scope,many)		Y
	# Big Icon			N (toc)			N (diff)			Y (used "promo")
	# --> This is used in the main Library view
	# Thumbnail			N (toc)			N					Y (not used)
	# Background		N (toc)			Y					N
	# Icon				N				Y (icon)			N (diff)
	# --> This is used in the hover menu for enrolled students
	# StartDate			Y				N					Y
	# Duration			Y				N					N
	# Schedule			Y				N					N
	# Email Sig			N				N					Y
	# Credit/Enroll		Y				N					N
	# Promo Video		Y				N					N
	# Prereqs			Y				N					N

	# Everything in the CourseInfo is also copied statically to a
	# data file used to render the landing page.

	# For packages with a CourseInfo, almost everything needed to
	# construct a purchasable can come from the courseinfo
	# or the ToC or convention (Big Icon) or be derived
	# (Preview and email sig).
	# The only thing missing is the 'featured' flag.

	if not package.courseInfoSrc:
		logger.debug("No course info for %s", package )
		return
	info_json_string = package.read_contents_of_sibling_entry( package.courseInfoSrc )
	info_json_dict = json.loads( info_json_string )

	global _last_json_dict # Temp testing
	_last_json_dict = info_json_dict

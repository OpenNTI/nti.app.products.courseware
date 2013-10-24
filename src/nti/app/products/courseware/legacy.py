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
	if not package.courseInfoSrc:
		logger.debug("No course info for %s", package )
		return
	info_json_string = package.read_contents_of_sibling_entry( package.courseInfoSrc )
	info_json_dict = json.loads( info_json_string )

	global _last_json_dict # Temp testing
	_last_json_dict = info_json_dict

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Externalization for catalog objects.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.externalization.autopackage import AutoPackageSearchingScopedInterfaceObjectIO

from . import interfaces

class _CoursewareObjectIO(AutoPackageSearchingScopedInterfaceObjectIO):

	@classmethod
	def _ap_enumerate_externalizable_root_interfaces(cls, cwr_interfaces):
		return (cwr_interfaces.ICourseCatalogEntry,
				cwr_interfaces.ICourseCatalogInstructorInfo,
				cwr_interfaces.ICourseCreditLegacyInfo)

	@classmethod
	def _ap_enumerate_module_names( cls ):
		return ('catalog', 'legacy')

_CoursewareObjectIO.__class_init__()

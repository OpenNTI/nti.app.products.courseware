#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.ntiids.ntiids import ROOT

@interface.implementer(ISearchPackageResolver)
class _RootSearchPacakgeResolver(object):

	def __init__(self, *args):
		pass

	def resolve(self, user, ntiid=None):
		result = set()
		if ntiid == ROOT:
			for enrollments in component.subscribers((user,), IPrincipalEnrollments):
				for enrollment in enrollments.iter_enrollments():
					course = ICourseInstance(enrollment, None)
					if course is None:  # dupped enrollment
						continue
					try:
						packages = course.ContentPackageBundle.ContentPackages
					except AttributeError:
						packages = (course.legacy_content_package,)

					for package in packages:
						ntiid = package.ntiid
						if ntiid:  # make sure we a valid ntiid
							result.add(package.ntiid)
		return result

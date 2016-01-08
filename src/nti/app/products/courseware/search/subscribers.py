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

from zope.intid.interfaces import IIntIds

from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_course_packages

from nti.ntiids.ntiids import ROOT

from nti.site.site import get_component_hierarchy_names

@interface.implementer(ISearchPackageResolver)
class _RootSearchPacakgeResolver(object):

	def __init__(self, *args):
		pass

	def resolve(self, user, ntiid=None):
		result = set()
		if ntiid == ROOT:
			catalog = get_enrollment_catalog()
			intids = component.getUtility(IIntIds)
			site_names = get_component_hierarchy_names()
			query = {
				IX_SITE:{'any_of': site_names},
				IX_USERNAME:{'any_of':(user.username,)}
			}
			for uid in catalog.apply(query) or ():
				context = intids.queryObject(uid)
				context = ICourseInstance(context, None)
				for package in get_course_packages(context):
					ntiid = package.ntiid
					if ntiid:  # make sure we a valid ntiid
						result.add(package.ntiid)
		return result

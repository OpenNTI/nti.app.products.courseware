#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 5

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

@interface.implementer(IDataserver)
class MockDataserver(object):

	root = None

	def get_by_oid(self, oid, ignore_creator=False):
		resolver = component.queryUtility(IOIDResolver)
		if resolver is None:
			logger.warn("Using dataserver without a proper ISiteManager configuration.")
		else:
			return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
		return None

def _decode(s):
	if not s:
		s = u''
	elif not isinstance(s, unicode):
		s = s.decode('utf-8', 'ignore')
	return s

def _migrate(current, seen):
	with current_site(current):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None or catalog.isEmpty():
			return
		for entry in catalog.iterCatalogEntries():
			ntiid = entry.ntiid
			if ntiid in seen:
				continue
			seen.add(ntiid)
			course = ICourseInstance(entry)
			course_discussions = ICourseDiscussions(course)
			if not course_discussions:
				continue
			for forum in course.Discussions.values():
				for topic_key, topic in forum.items():
					if topic_key != topic.__name__:
						logger.info('In course %s, renaming "%s" to "%s"',
									ntiid, topic.__name__, topic_key)
						topic.__name__ = topic_key

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	mock_ds = MockDataserver()
	mock_ds.root = ds_folder
	component.provideUtility(mock_ds, IDataserver)

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		seen = set()
		for current in get_all_host_sites():
			_migrate(current, seen)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 5 by adjusting discussion topic keys
	"""
	do_evolve(context, generation)

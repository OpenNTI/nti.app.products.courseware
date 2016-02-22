#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 2

from itertools import chain

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.app.products.courseware.discussions import get_acl
from nti.app.products.courseware.discussions import auto_create_forums
from nti.app.products.courseware.discussions import discussions_forums
from nti.app.products.courseware.discussions import announcements_forums

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.ntiids.ntiids import make_specific_safe

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

def _adjust_acls(current, seen):
	with current_site(current):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None or catalog.isEmpty():
			return
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid in seen:
				continue
			seen.add(entry.ntiid)
			course = ICourseInstance(entry)
			if course is not None and auto_create_forums(course):
				count = 0
				discussions = course.Discussions
				for forum in chain(discussions_forums(course),
								   announcements_forums(course)):
					safe_name = make_specific_safe(forum.name)
					new_acl = get_acl(course, forum.scope.NTIID)
					# Get our actual forum
					try:
						forum = discussions[safe_name]
						forum.__acl__ = new_acl
						count += 1
						logger.info('[%s] Updating forum acls for %s (count=%s)',
									current.__name__, entry.ntiid, count)
					except KeyError:
						pass

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
			_adjust_acls(current, seen)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 2 by adjusting bundled discussion ACLs.
	"""
	do_evolve(context, generation)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 3

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.contentfile.interfaces import IContentBlobFile
from nti.contentfile.interfaces import IContentBlobImage

from nti.contentfolder.interfaces import IContentFolder
	
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

def _adjust_item(item):
	if IContentFolder.providedBy(item):
		for x in item.values():
			_adjust_item(x)
		if 		not ICourseRootFolder.providedBy(item) \
			and not ICourseContentFolder.providedBy(item):
			interface.alsoProvides(item, ICourseContentFolder)
	elif 	IContentBlobFile.providedBy(item) \
		and not ICourseContentFile.providedBy(item):
			interface.alsoProvides(item, ICourseContentFile)
	elif	IContentBlobImage.providedBy(item) \
		and not ICourseContentImage.providedBy(item):
			interface.alsoProvides(item, ICourseContentImage)
			
def _adjust_course(current, seen):
	with current_site(current):
		catalog = component.queryUtility(ICourseCatalog)
		if catalog is None or catalog.isEmpty():
			return
		for entry in catalog.iterCatalogEntries():
			if entry.ntiid in seen:
				continue
			seen.add(entry.ntiid)
			course = ICourseInstance(entry)
			resources = course_resources(course, create=False)
			if resources is not None:
				_adjust_item(resources)

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
			_adjust_course(current, seen)
	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 3 by adjusting bundled discussion ACLs.
	"""
	do_evolve(context, generation)

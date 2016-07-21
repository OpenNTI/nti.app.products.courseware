#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 8

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.resources.adapters import course_resources

from nti.contentfile.interfaces import IContentBaseFile

from nti.contentfolder.interfaces import INamedContainer

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

def _transformer(container, intids):
	for value in list(container.values()):
		if INamedContainer.providedBy(value):
			_transformer(value, intids)
		elif IContentBaseFile.providedBy(value) and value.has_associations():
			for obj in list(value.associations()):
				value.remove_association(obj)
				if intids.queryId(obj) is not None:
					value.add_association(obj)

def _migrate(current, seen, intids):
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
			resources = course_resources(course, create=False)
			if resources:
				_transformer(resources, intids)

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
		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		for current in get_all_host_sites():
			_migrate(current, seen, intids)

	component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 8 by recreating the file associations
	"""
	do_evolve(context, generation)

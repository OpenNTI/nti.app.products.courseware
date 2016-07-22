#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 10

import re

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.resources import CourseContentFile
from nti.app.products.courseware.resources import CourseContentImage

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.utils import is_internal_file_link
from nti.app.products.courseware.resources.utils import to_external_file_link
from nti.app.products.courseware.resources.utils import get_file_from_external_link
	
from nti.contentfolder.interfaces import INamedContainer

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

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

def _convert(name, value, container):
	result = CourseContentFile()
	result.data = value.data
	result.filename = value.filename
	result.__name__ = result.name = name
	result.contentType = getattr(value, 'contentType', None)
	
	# XXX: Check for invalid filename
	m = re.match(r"\(u'(.*)', u'(.*)'\)", value.filename)
	if m is not None:
		result.filename = m.groups()[0]
				
	# update container
	del container[name]
	container[name] = result
	return result

def _transformer(container, catalog, intids):
	for name, value in list(container.items()):	
		if INamedContainer.providedBy(value):
			_transformer(value, intids)
		elif not isinstance(value, (CourseContentFile, CourseContentImage)):
			_convert(name, value, container)

def _rebase_assets(site, entry, catalog, intids):
	items = catalog.search_objects(sites=site.__name__,
						  		   provided=INTIRelatedWorkRef,
						  		   container_ntiids=entry.ntiid,
						  		   intids=intids)	
	for item in items:	
		for name in ('href', 'icon'):
			value = getattr(item, name, None)
			if is_internal_file_link(value or u''):
				source = get_file_from_external_link(value)
				if source is None:
					continue
				if not isinstance(value, (CourseContentFile, CourseContentImage)):
					name = source.__name__
					container = source.__parent__
					if 		ICourseContentFolder.providedBy(container) \
						or	ICourseRootFolder.providedBy(container):
						source = _convert(name, source, container)
						link = to_external_file_link(source)
						setattr(item, name, link)
				if hasattr(source, "add_association"):
					source.add_association(item)
			
def _migrate(current, seen, intids):
	libray_catalog = get_library_catalog()
	with current_site(current):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			doc_id = intids.queryId(course)
			if doc_id is None or doc_id in seen:
				continue
			seen.add(doc_id)
			_rebase_assets(current, entry, libray_catalog, intids)
			resources = course_resources(course, create=False)
			if resources is not None:
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
	Evolve to generation 10 to make all course files of the same class
	"""
	do_evolve(context)

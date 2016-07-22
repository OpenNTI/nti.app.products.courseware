#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 6

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.filer import is_image
from nti.app.products.courseware.resources.filer import get_unique_file_name

from nti.app.products.courseware.resources.utils import get_images_folder
from nti.app.products.courseware.resources.utils import get_documents_folder

from nti.common.string import to_unicode

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

def _mover(container, images, documents):
	if container is images or container  is documents:
		return

	for name, value in list(container.items()):
		
		if value is images or value  is documents:
			continue
			
		if INamedContainer.providedBy(value):
			_mover(value, images, documents)
		else:
			contentType = getattr(value, 'contentType', None)
			if is_image(name, contentType):
				target = images
			else:
				target = documents
			target_name, filename = get_unique_file_name(name,  target)
			if target_name != name:
				value.name = to_unicode(target_name)
				value.filename = to_unicode(filename)
			container.moveTo(value, target, target_name)

	if not container:
		del container.__parent__[container.name] # remove empty directory

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
			resources = course_resources(course, create=False)
			if not resources:
				continue
			images = get_images_folder(course)
			documents = get_documents_folder(course)
			_mover(resources, images, documents)

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
	Evolve to generation 6 by moving course files
	"""
	do_evolve(context, generation)

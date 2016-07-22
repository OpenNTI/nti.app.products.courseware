#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 9

import re

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from nti.app.products.courseware.generations import evolve6

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.utils import get_images_folder
from nti.app.products.courseware.resources.utils import get_documents_folder

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

def _transformer(container):
	for name, value in list(container.items()):	
		if INamedContainer.providedBy(value):
			_transformer(value)
		else:
			m  = re.match(r"\((.*),(.*)\)", name)
			if m and m.groups()[0] == m.groups()[1]:
				value.filename = m.groups()[0]
				container._delitemf(name, event=False)
				value.__name__ = value.name = m.groups()[0]
				container._setitemf(value.name, value)
				logger.warn("%s was renamed to %s", name, value.filename)

def _migrate(current, seen):
	with current_site(current):
		catalog = component.queryUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			ntiid = entry.ntiid
			if ntiid in seen:
				continue
			seen.add(ntiid)
			course = ICourseInstance(entry)
			resources = course_resources(course, create=False)
			if not resources:
				continue
			_transformer(resources)
			# move to images / documents
			images = get_images_folder(course)
			documents = get_documents_folder(course)
			evolve6.mover(resources, images, documents)

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
	Evolve to generation 9 by fixing bad migration.
	"""
	do_evolve(context, generation)

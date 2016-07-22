#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 10

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources import CourseContentFile
from nti.app.products.courseware.resources import CourseContentImage

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
	for name, value in list(container.items()):	
		if INamedContainer.providedBy(value):
			_transformer(value)
		elif not isinstance(value, (CourseContentFile, CourseContentImage)):
			new_value = CourseContentFile()
			new_value.data = value.data
			new_value.filename = value.filename
			new_value.__name__ = new_value.name = name
			new_value.contentType = getattr(value, 'contentType', None)
			
			# update associations
			if hasattr(value, 'associations'):
				associations =  list(value.associations())
				value.clear_associations()
				[new_value.add_association(x) for x in associations]
				
			# update container
			container._delitemf(name, event=False)
			container._setitemf(name, new_value)
			new_value.__parent__ = value.__parent__

			# update w/ intid
			doc_id = intids.getId(value)
			intids.forceUnregister(doc_id, notify=False)
			intids.forceRegister(doc_id, new_value)
			
			value.__parent__ = None # ground
			
def _migrate(current, seen, intids):
	with current_site(current):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry)
			doc_id = intids.getId(course)
			if doc_id in seen:
				continue
			seen.add(doc_id)
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
	Evolve to generation 10 by making all files course files of a single class
	"""
	do_evolve(context, generation)

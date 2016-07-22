#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 7

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.component.hooks import site as current_site

from nti.app.products.courseware.resources.interfaces import ICourseLockedFolder

from nti.app.products.courseware.resources.utils import get_images_folder
from nti.app.products.courseware.resources.utils import get_documents_folder

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.site.hostpolicy import get_all_host_sites

def _convert_to_locked_folders(current, seen, intids):
	with current_site(current):
		catalog = component.getUtility(ICourseCatalog)
		for entry in catalog.iterCatalogEntries():
			course = ICourseInstance(entry, None)
			doc_id = intids.queryId(course)
			if doc_id is None or doc_id in seen:
				continue
			seen.add(doc_id)
			for get_folder in (get_documents_folder, get_images_folder):
				folder = get_folder(course)
				if not ICourseLockedFolder.providedBy(folder):
					interface.alsoProvides(folder, ICourseLockedFolder)

def do_evolve(context, generation=generation):
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']

	with current_site(ds_folder):
		assert	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		seen = set()
		lsm = ds_folder.getSiteManager()
		intids = lsm.getUtility(IIntIds)
		for current in get_all_host_sites():
			_convert_to_locked_folders(current, seen, intids)

	logger.info('Evolution %s done.', generation)

def evolve(context):
	"""
	Evolve to generation 7 by locking course root folders.
	"""
	do_evolve(context, generation)

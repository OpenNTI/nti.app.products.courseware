#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 18

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.resources.adapters import course_resources

from nti.contentfolder.interfaces import INamedContainer

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites


def process_course_resources(container):
    for key, value in list(container.items()):
        modify = False
        if INamedContainer.providedBy(value):
            # remove unused attribute
            if 'use_blobs' in value.__dict__:
                delattr(value, 'use_blobs')
                modify = True
            # name and filename are now alias of __name__
            # remove filename if in dict
            if 'filename' in value.__dict__:
                del value.__dict__['filename']
                modify = True
            process_course_resources(value)
        else:
            # __name__ is now an alias of 'filename'
            # make sure filename is in dict or has the correct value
            if 'filename' not in value.__dict__ \
                    or value.__dict__['filename'] != key:
                value.filename = key
                modify = True
            # name may be redundant
            if 'name' in value.__dict__ \
                    and value.__dict__['name'] == key:
                del value.__dict__['name']
                modify = True
        if modify:
            value._p_changed = True
            lifecycleevent.modified(value)


def _process_site(current, intids, seen):
    with current_site(current):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            resources = course_resources(course, create=False)
            if resources:
                process_course_resources(resources)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        seen = set()
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        for current in get_all_host_sites():
            _process_site(current, intids, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 18 by fixing aliased attributes in contentfiles and folders
    """
    do_evolve(context)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.interfaces import ICourseSharingScopeUtility

from nti.app.products.courseware.sharing_scopes import CourseSharingScopeUtility

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

from nti.site.localutility import install_utility

generation = 21

logger = __import__('logging').getLogger(__name__)


def _process_site(current, intids, seen, sharing_scope_utility):
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
            for scope in course.SharingScopes.values():
                sharing_scope_utility.add_scope(scope)


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
            sharing_scope_utility = CourseSharingScopeUtility()
            _process_site(current, intids, seen, sharing_scope_utility)
            install_utility(sharing_scope_utility,
                            '++etc++CourseSharingScopeUtility',
                            ICourseSharingScopeUtility,
                            current.getSiteManager())

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 21 by the course sharing scope utility for all sites.
    """
    do_evolve(context)

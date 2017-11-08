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

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.zope_catalog.interfaces import IDeferredCatalog

CATALOG_NAME = 'nti.dataserver.++etc++course-resources'

generation = 14

logger = __import__('logging').getLogger(__name__)


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

        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        catalog = lsm.queryUtility(IDeferredCatalog, name=CATALOG_NAME)
        if catalog is not None:
            catalog.__parent__ = None
            intids.unregister(catalog)
            for name, index in list(catalog.items()):
                del catalog[name]
                index.__parent__ = None
                intids.unregister(index)
                try:
                    index.clear()
                except AttributeError:
                    pass
            lsm.unregisterUtility(provided=IDeferredCatalog, name=CATALOG_NAME)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 14 by removing course resource catalog
    """
    do_evolve(context)

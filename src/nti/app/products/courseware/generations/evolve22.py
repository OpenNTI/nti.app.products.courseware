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

from nti.app.products.courseware.interfaces import ICourseSharingScopeUtility

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.site.hostpolicy import get_all_host_sites

from nti.app.users.utils import get_site_admins

generation = 22

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

        for current in get_all_host_sites():
            site_count = 0
            csm = current.getSiteManager()
            sharing_scope_utility = csm.getUtility(ICourseSharingScopeUtility)
            site_admins = get_site_admins(current)
            for scope in sharing_scope_utility.iter_scopes(parent_scopes=True):
                for site_admin in site_admins:
                    site_count += 1
                    site_admin.follow(scope)
            logger.info('[%s] Site admins following course scopes (%s)',
                        current.__name__, site_count)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 22 by ensuring site admins `follow` all course
    sharing scopes.
    """
    do_evolve(context)

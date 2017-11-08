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

from nti.base._compat import text_

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.invitations.interfaces import IInvitationsContainer

from nti.invitations.index import IX_SITE
from nti.invitations.index import get_invitations_catalog

from nti.site.hostpolicy import get_host_site
from nti.site.hostpolicy import get_all_host_sites

generation = 16

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


def _find_site(doc_id, invitation, site_index, seen):
    course = invitation.course
    site_name = seen.get(course)
    if not site_name:
        for site in get_all_host_sites():
            with current_site(site):
                catalog = component.queryUtility(ICourseCatalog)
                if catalog is None or catalog.isEmpty():
                    continue
                for entry in catalog.iterCatalogEntries():
                    if entry.ntiid == course:
                        site_name = site.__name__
                        break
            if site_name:
                break
    # set and index if found
    if site_name:
        invitation.site = text_(site_name)
        with current_site(get_host_site(site_name)):
            site_index.index_doc(doc_id, invitation)
        seen[course] = site_name


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        seen = {}
        lsm = ds_folder.getSiteManager()
        intids = lsm.getUtility(IIntIds)
        catalog = get_invitations_catalog()
        site_index = catalog[IX_SITE]
        invitations = component.getUtility(IInvitationsContainer)
        for invitation in list(invitations.values()):
            doc_id = intids.queryId(invitation)
            if doc_id is None:
                continue
            try:
                site_name = site_index.documents_to_values[doc_id]
                if site_name:
                    invitation.site = text_(site_name)
                    continue
            except KeyError:
                pass

            if not IJoinCourseInvitation.providedBy(invitation):
                invitation.site = u"dataserver2"
            else:
                _find_site(doc_id, invitation, site_index, seen)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 16 by setting the proper site name to invitations
    """
    do_evolve(context)

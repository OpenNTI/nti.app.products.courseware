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

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.intid.common import removeIntId

from nti.traversal.traversal import find_interface

generation = 19

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator)
        return None


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        catalog = get_metadata_catalog()
        intids = component.getUtility(IIntIds)
        query = {
            IX_MIMETYPE: {'any_of': ('application/vnd.nextthought.courses.discussion',)},
        }
        for doc_id in catalog.apply(query) or ():
            obj = intids.queryObject(doc_id)
            if not ICourseDiscussion.providedBy(obj):
                continue
            course = find_interface(obj, ICourseInstance, strict=False)
            doc_id = intids.queryId(course)
            if doc_id is None:  # invalid course
                container = find_interface(obj, ICourseDiscussions, strict=False)
                if container is not None:
                    container.clear()
                if intids.queryId(obj) is not None:
                    removeIntId(obj)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Evolution %s done.', generation)


def evolve(context):
    """
    Evolve to generation 19 by removing ghost course discussions
    """
    do_evolve(context)

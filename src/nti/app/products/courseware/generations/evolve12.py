#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 12

from urlparse import unquote

from zope import component
from zope import interface

from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.resources.adapters import course_resources

from nti.app.products.courseware.resources.utils import to_external_file_link

from nti.contentfolder.interfaces import INamedContainer

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.externalization.oids import to_external_ntiid_oid

from nti.ntiids.ntiids import is_valid_ntiid_string

from nti.site.hostpolicy import get_all_host_sites


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


def _fix_pointers(container):
    for name, value in list(container.items()):
        if INamedContainer.providedBy(value):
            _fix_pointers(value)
        elif value.has_associations():
            href = to_external_file_link(value)
            target = to_external_ntiid_oid(value)
            unquoted_href = unquote(href)
            for obj in value.associations():
                if not INTIRelatedWorkRef.providedBy(obj):
                    continue
                # if href is equal continue
                if unquote(obj.href or '') == unquoted_href:
                    # make sure we have a valid target
                    if not hasattr(obj, 'target') or obj.target != target:
                        obj.target = target
                    continue
                # if target is equal continue
                if hasattr(obj, 'target') and obj.target == target:
                    # make sure we have a valid href
                    if     not hasattr(obj, 'href') \
                        or (    unquote(obj.href or '') != unquoted_href
                            and not is_valid_ntiid_string(obj.href or '')):
                        obj.href = href
                    continue
                # if icon continue
                unquoted_icon = unquote(obj.icon or '') if hasattr(obj, 'icon') else ''
                if unquoted_icon == unquoted_href:
                    continue
                # update icon if found in file name
                if name in unquoted_icon or value.filename in unquoted_icon:
                    logger.info('Updating [%s] icon url to %s', 
                                obj.ntiid, href)
                    obj.icon = href
                    continue
                logger.info('Updating [%s] href url to %s', obj.ntiid, href)
                logger.info('Updating [%s] target to %s', obj.ntiid, target)
                # otherwise update href
                obj.href = href
                obj.target = target


def _migrate(current, seen, intids):
    with current_site(current):
        catalog = component.queryUtility(ICourseCatalog)
        if catalog is None or catalog.isEmpty():
            return
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            resources = course_resources(course, create=False)
            if resources is not None:
                _fix_pointers(resources)


def do_evolve(context, generation=generation):
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with current_site(ds_folder):
        assert  component.getSiteManager() == ds_folder.getSiteManager(), \
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
    Evolve to generation 12 to fix href/icon pointers
    """
    do_evolve(context)

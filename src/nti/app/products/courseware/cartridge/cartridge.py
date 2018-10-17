#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from collections import defaultdict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_content_units

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation import INTIVideo

from nti.site.site import get_component_hierarchy_names

from nti.contenttypes.presentation.interfaces import INTIAudio
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.schema.interfaces import find_most_derived_interface


__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


CC_PRESENTATION_ASSET_IFACES = {INTIVideo: 'videos',
                                INTIAudio: 'audio'}


def get_all_package_assets(course):
    catalog = get_library_catalog()
    intids = component.getUtility(IIntIds)
    container_ntiids = {item.ntiid for item in get_course_content_units(course)}
    entry = ICourseCatalogEntry(course)
    container_ntiids.add(entry.ntiid)
    query = catalog.search_objects(intids=intids,
                                   container_all_of=False,
                                   container_ntiids=container_ntiids,
                                   sites=get_component_hierarchy_names(),
                                   provided=CC_PRESENTATION_ASSET_IFACES.keys())
    return query.items()


@component.adapter(ICourseInstance)
@interface.implementer(IIMSCommonCartridge)
class IMSCommonCartridge(object):

    def __init__(self, course):
        self.course = course

    @Lazy
    def cartridge_web_content(self):
        assets = get_all_package_assets(self.course)
        web_content = defaultdict(list)
        for (unused_intid, asset) in assets:
            iface = find_most_derived_interface(asset, IPresentationAsset)
            # This should always resolve as the keys are used to query these assets
            key = CC_PRESENTATION_ASSET_IFACES[iface]
            web_content[key].append(IIMSWebContentUnit(asset))
        return web_content

    @property
    def learning_application_objects(self):
        raise NotImplementedError

    @property
    def manifest(self):
        raise NotImplementedError

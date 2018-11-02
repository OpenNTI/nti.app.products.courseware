#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from lxml import etree

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge
from nti.app.products.courseware.cartridge.interfaces import IIMSResource
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.common.datastructures import ObjectHierarchyTree

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_content_units

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.site.site import get_component_hierarchy_names

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


CC_PRESENTATION_ASSET_IFACES = {INTIRelatedWorkRef: 'resources'}


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

    resources = dict()
    errors = []

    def __init__(self, course):
        self.course = course
        self.manifest_resources = etree.Element(u'resources')

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @Lazy
    def course_tree(self):
        def _lookup_func(obj):
            intids = component.getUtility(IIntIds)
            return intids.queryId(obj)

        def _recur_lesson(lesson):
            for asset in lesson.Items or ():
                tree.add(asset, parent=lesson)
                # We don't want to iterate down into media rolls etc, only map what the
                # course structure actually looks like in the UI
                if IGroupOverViewable.providedBy(asset):
                    continue
                else:
                    _recur_lesson(asset)

        def _recur_nodes(node):
            for child in node.values():
                lesson = INTILessonOverview(child, None)
                if lesson:
                    tree.add(lesson, parent=node)
                    _recur_lesson(lesson)
                else:
                    tree.add(child, parent=node)
                    _recur_nodes(child)

        tree = ObjectHierarchyTree(lookup_func=_lookup_func)
        # There is a little magic around the Outline property that will create one if it doesn't exist
        # so we are safe here grabbing whatever is there. In the typical case, we would expect the
        # Outline to already exist and have nodes
        tree.set_root(self.course.Outline)
        _recur_nodes(self.course.Outline)
        return tree


def build_manifest_items(cartridge):
    course_tree = cartridge.course_tree
    resources = cartridge.resources
    errors = cartridge.errors
    # Create the root
    items = etree.Element(u'item', identifier=u'LearningModules')
    intids = component.getUtility(IIntIds)

    # TODO handle non published items
    # Recurse through the tree
    def _recur_items(tree, xml_node):
        if not tree.children:
            return
        for node in tree.children:
            obj = node.obj

            # convert to common cartridge item if some type of asset
            if IGroupOverViewable.providedBy(obj):
                try:
                    # make sure we have a concrete asset
                    obj = IConcreteAsset(obj, obj)
                    # creates an id if none exists, or returns the existing one
                    identifier = intids.register(obj)
                    properties = {'identifier': unicode(identifier)}
                    resource = IIMSResource(obj)
                    resources[identifier] = resource  # Map this object to it's common cartridge resource
                    properties['identifierref'] = unicode(resource.identifier)
                except TypeError:  # Likely incrementally faster than if/else as we expect these to resolve normally
                    logger.warning(u'Unable to export %s to common cartridge' % obj.__class__)
                    errors.append(CommonCartridgeExportException(u'Unsupported asset type: %s' % obj.__class__))
                    _recur_items(node, xml_node)
                    continue
            else:
                identifier = intids.register(obj)
                properties = {'identifier': unicode(identifier)}
            # Add this item entry
            item = etree.SubElement(xml_node, u'item', **properties)
            title = etree.SubElement(item, u'title')
            title.text = getattr(obj, 'title', '') or getattr(obj, 'label', '')
            _recur_items(node, item)

    _recur_items(course_tree, items)
    return etree.tostring(items, pretty_print=True)


def build_cartridge_content(cartridge):
    assets = get_all_package_assets(cartridge.course)
    resources = cartridge.resources
    intids = component.getUtility(IIntIds)
    for (unused_intid, asset) in assets:
        nti_intid = intids.register(asset)
        if nti_intid not in resources:
            unit = IIMSWebContentUnit(asset, None)
            if unit is not None:  # TODO fix
                resources[nti_intid] = unit

#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from collections import defaultdict

from lxml import etree

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.component import subscribers

from zope.intid import IIntIds

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridgeExtension
from nti.app.products.courseware.cartridge.interfaces import IIMSManifestResources
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
from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.schema.interfaces import find_most_derived_interface


__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


CC_PRESENTATION_ASSET_IFACES = {INTIRelatedWorkRef: 'resources'}
CARTRIDGE_WEB_CONTENT_FOLDER = 'web_resources'  # This folder name is undefined in the spec


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


class CartridgeWebContent(object):

    content = None

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    def __init__(self, course):
        assets = get_all_package_assets(course)
        resources = component.getUtility(IIMSManifestResources)()
        self.content = defaultdict(dict)
        for (unused_intid, asset) in assets:
            iface = find_most_derived_interface(asset, IPresentationAsset)
            # This should always resolve as the keys are used to query these assets
            key = CC_PRESENTATION_ASSET_IFACES[iface]
            unit = IIMSWebContentUnit(asset, None)
            if unit is not None:
                identifier_ref = self.intids.register(asset)
                self.content[key][identifier_ref] = unit
                path = '%s/%s/' % (CARTRIDGE_WEB_CONTENT_FOLDER, key)
                href = path + unit.filename
                resource = etree.SubElement(resources, u'resource', identifier=unicode(unit.identifier), type=unit.type, href=href)
                etree.SubElement(resource, u'file', href=href)
                for (key, deps) in unit.dependencies.items():
                    for dep in deps:
                        etree.SubElement(resource, u'dependency', identifierref=unicode(dep.identifier))
                        href = os.path.join(path, unit.dirname, key, dep.filename)
                        d_res = etree.SubElement(resources, u'resource', identifier=unicode(dep.identifier), type=unit.type, href=href)
                        etree.SubElement(d_res, u'file', href=href)
                # Register this unit, we will use this intid as the 'identifierref'
                self.intids.register(unit)

    def __getitem__(self, item):
        return self.content.__getitem__(item)

    def get(self, item):
        return self.content.get(item)

    def values(self):
        return self.content.values()

    def keys(self):
        return self.content.keys()

    def items(self):
        return self.content.items()

    def __setitem__(self, key, value):
        self.content.__setitem__(key, value)

    def setdefault(self, key, default):
        self.content.setdefault(key, default)

    def _recursive_lookup(self, key, dictionary):
        if key in dictionary:
            return dictionary[key]
        for value in dictionary.values():
            if isinstance(value, dict):
                result = self._recursive_lookup(key, value)
                if result is not None:
                    return result
        return None

    def find(self, item):
        return self._recursive_lookup(item, self.content)


@component.adapter(ICourseInstance)
@interface.implementer(IIMSCommonCartridge)
class IMSCommonCartridge(object):

    def __init__(self, course):
        self.course = course
        self.cartridge_web_content = CartridgeWebContent(course)

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

    @property
    def learning_application_objects(self):
        raise NotImplementedError

    @property
    def manifest(self):
        raise NotImplementedError

    @property
    def extensions(self):
        return subscribers([self], IIMSCommonCartridgeExtension)


def build_manifest_items(cartridge):
    course_tree = cartridge.course_tree
    cwc = cartridge.cartridge_web_content
    # Create the root
    items = etree.Element(u'item', identifier=u'LearningModules')
    intids = component.getUtility(IIntIds)
    resources = component.getUtility(IIMSManifestResources)

    # Recurse through the tree
    def _recur_items(tree, xml_node):
        if not tree.children:
            return
        for node in tree.children:
            obj = node.obj
            # make sure we have a concrete asset
            obj = IConcreteAsset(obj, obj)
            identifier = intids.register(obj)  # This creates an id if none exists, or returns the existing one
            content_unit = cwc.find(identifier)
            identifier_ref = intids.queryId(content_unit)
            properties = {'identifier': unicode(identifier)}
            # Check if we have already processed this item
            if identifier_ref:
                properties['identifierref'] = unicode(identifier_ref)
            # Check if this is an asset that needs processed
            elif not identifier_ref and IPresentationAsset.providedBy(obj):
                resource = IIMSResource(obj, None)
                if resource is None:
                    logger.log(u'Unsupported asset type: %s' % obj)
            item = etree.SubElement(xml_node, u'item', **properties)
            title = etree.SubElement(item, u'title')
            title.text = getattr(obj, 'title', '') or getattr(obj, 'label', '')
            _recur_items(node, item)

    _recur_items(course_tree, items)
    return etree.tostring(items, pretty_print=True)


@interface.implementer(IIMSManifestResources)
class IMSManifestResources(object):

    def __init__(self):
        self.resources = etree.Element(u'resources')

    def __call__(self):
        return self.resources

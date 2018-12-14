#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os

from lxml import etree

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy
from zope.component import queryMultiAdapter
from zope.interface.interfaces import ComponentLookupError

from zope.intid import IIntIds
from zope.proxy import getProxiedObject

from nti.app.assessment.common.evaluations import get_course_evaluations, get_course_assignments
from nti.app.products.courseware import cartridge
from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge, IIMSUnsortedContent, \
    ICommonCartridgeAssessment
from nti.app.products.courseware.cartridge.interfaces import IIMSResource
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit
from nti.assessment.interfaces import DISCUSSION_ASSIGNMENT_MIME_TYPE, ASSIGNMENT_MIME_TYPE, QUESTION_SET_MIME_TYPE, \
    TIMED_ASSIGNMENT_MIME_TYPE, IQuestionSet

from nti.common.datastructures import ObjectHierarchyTree

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.common import get_course_content_units

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.site.site import get_component_hierarchy_names

from nti.contenttypes.presentation.interfaces import IConcreteAsset, INTIAssessmentRef, INTIMediaRoll
from nti.contenttypes.presentation.interfaces import IGroupOverViewable
from nti.contenttypes.presentation.interfaces import INTILessonOverview
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.ntiids.ntiids import find_object_with_ntiid

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

    def __init__(self, course):
        self.course = course
        self.manifest_resources = etree.Element(u'resources')
        self.resources = dict()
        self.errors = []

    def export_errors(self, dirname):
        with open(os.path.join(dirname, 'web_resources', 'nti_export_errors.txt'), 'w') as export_errors:
            export_errors.write('\n'.join([e.message for e in self.errors]).encode('utf-8'))
        item = etree.SubElement(self.manifest_resources, u'resource',
                                identifier=u'NTIEXPORTERRORS',
                                type='webcontent',
                                href='web_resources/nti_export_errors.txt')
        etree.SubElement(item, u'file', href='web_resources/nti_export_errors.txt')

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
                    asset = IConcreteAsset(obj, obj)
                    # resolve assessments
                    if INTIAssessmentRef.providedBy(asset):
                        asset = find_object_with_ntiid(obj.target)
                    if INTIMediaRoll.providedBy(obj):
                        # Exclude empty video rolls
                        if not bool(obj.Items):
                            continue
                    # creates an id if none exists, or returns the existing one
                    intid = intids.register(asset)
                    identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
                    properties = {'identifier': unicode(identifier)}
                    if identifier not in resources:
                        resource = IIMSResource(asset, None)
                        if resource is None:
                            logger.warning(u'Unable to export %s to common cartridge' % obj.__class__)
                            errors.append(CommonCartridgeExportException(u'Unsupported asset type: %s' % obj.__class__))
                            _recur_items(node, xml_node)
                            continue
                        resources[identifier] = resource  # Map this object to it's common cartridge resource
                    else:
                        resource = resources[identifier]
                    properties['identifierref'] = unicode(resource.identifier)
                except CommonCartridgeExportException as e:  # Likely incrementally faster than if/else as we expect these to resolve normally
                    errors.append(e)
                    _recur_items(node, xml_node)
                    continue
            else:
                intid = intids.register(obj)
                identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
                properties = {'identifier': unicode(identifier)}
            # Add this item entry
            item = etree.SubElement(xml_node, u'item', **properties)
            title = etree.SubElement(item, u'title')
            title.text = getattr(obj, 'title', '') or getattr(obj, 'label', '')
            _recur_items(node, item)

    _recur_items(course_tree, items)
    return etree.tounicode(items, pretty_print=True)


# TODO Concrete?
def build_cartridge_content(cartridge):
    resources = cartridge.resources
    intids = component.getUtility(IIntIds)

    # XXX: Content packages are mangled causing unrelated course files to be exported down this path
    # assets = get_all_package_assets(cartridge.course)
    # for (unused_intid, asset) in assets:
    #     intid = intids.register(asset)
    #     identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
    #     if identifier not in resources:
    #         try:
    #             unit = IIMSWebContentUnit(asset, None)
    #             if unit is not None:  # TODO fix
    #                 resources[identifier] = unit
    #         except CommonCartridgeExportException as e:
    #             cartridge.errors.append(e)

    # Assignments not in course structure
    assessments = get_course_assignments(cartridge.course,
                                         sort=False,
                                         parent_course=True)
    for assessment in assessments:
        assessment = getProxiedObject(assessment)
        intid = intids.register(assessment)
        identifier = ''.join([chr(65 + int(i)) for i in str(intid)])
        if identifier not in resources:
            try:
                unit = ICommonCartridgeAssessment(assessment, None)
                if unit is not None:
                    logger.info(u'Added unsorted assignment %s' % assessment.title)
                    interface.alsoProvides(IIMSUnsortedContent)
                    resources[identifier] = unit
            except CommonCartridgeExportException as e:
                cartridge.errors.append(e)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from nti.contentlibrary.interfaces import IContentPackageBundle
from nti.contentlibrary.interfaces import IContentUnitHrefMapper

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.legacy_catalog import ICourseCatalogLegacyEntry

from nti.ntiids.ntiids import get_parts
from nti.ntiids.ntiids import make_ntiid

from nti.store.course import create_course
from nti.store.interfaces import IPurchasableCourse

from .interfaces import ILegacyCommunityBasedCourseInstance

@interface.implementer(IContentPackageBundle)
@component.adapter(ILegacyCommunityBasedCourseInstance)
def _legacy_course_to_content_package_bundle(course):
    return course.ContentPackageBundle

@interface.implementer(IContentPackageBundle)
@component.adapter(IContentCourseInstance)
def _course_content_to_package_bundle(course):
    return course.ContentPackageBundle

@interface.implementer(IContentPackageBundle)
@component.adapter(ICourseCatalogEntry)
def _entry_to_content_package_bundle(entry):
    course = ICourseInstance(entry, None)
    return IContentPackageBundle(course, None)
 
@interface.implementer(IPurchasableCourse)
@interface.implementer(ICourseCatalogEntry)
def _entry_to_purchasable(entry):
    course_instance = ICourseInstance(entry, None)
    result = IPurchasableCourse(course_instance, None)
    return result
    
@interface.implementer(IPurchasableCourse)
@interface.implementer(ICourseInstance)
def _course_to_purchasable(course):
    entry = ICourseCatalogEntry(course, None)
    if entry is None:
        return None

    parts = get_parts(entry.NTIID)
    ntiid = make_ntiid(date=parts.date, provider=parts.provider,
                       nttype="PurchasableCourse", specific=parts.specific)
 
    preview = False
    icon = thumbnail = None
    if ICourseCatalogLegacyEntry.provided(entry):
        preview = entry.Preview
        icon = entry.LegacyPurchasableIcon
        thumbnail = entry.LegacyPurchasableThumbnail

    items = ()
    bundle = getattr(course, 'ContentPackageBundle', None)
    if bundle is not None:
        packages = [x for x in bundle.ContentPackages]
        items = [x.ntiid for x in bundle.ContentPackages]
        if icon is None and packages:
            pkg = packages[0]
            icon = IContentUnitHrefMapper(pkg.icon).href if pkg.icon else None
        if thumbnail is None and packages:
            pkg = packages[0]
            thumbnail = IContentUnitHrefMapper(pkg.thumbnail).href if pkg.thumbnail else None
        
    result = create_course(ntiid=ntiid,
                           items=items,
                           name=entry.title, 
                           title=entry.title,
                           provider=parts.provider, 
                           description=entry.description,
                           # deprecated/legacy
                           icon=icon,
                           preview=preview,
                           thumbnail=thumbnail,
                           startdate=entry.StartDate,
                           signature=entry.InstructorsSignature,
                           department=entry.ProviderDepartmentTitle)
    
    return result


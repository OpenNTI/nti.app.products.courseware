#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.traversal import find_interface

import zope.intid
from zope import interface
from zope import component

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance

from nti.dataserver.interfaces import IUser

from .interfaces import ILegacyCommunityBasedCourseInstance
from .interfaces import ILegacyCourseConflatedContentPackageUsedAsCourse

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

@interface.implementer(ICourseInstance)
@component.adapter(ILegacyCourseConflatedContentPackageUsedAsCourse)
def _course_content_package_to_course(package):
    # Both the catalog entry and the content package are supposed to
    # be non-persistent (in the case we actually get a course) or the
    # course doesn't exist (in the case that the package is persistent
    # and installed in a sub-site, which shouldn't happen with this
    # registration, though could if we used a plain
    # ConflatedContentPackage), so it should be safe to cache this on
    # the package. Be extra careful though, just in case.
    cache_name = '_v_course_content_package_to_course'
    course_intid = getattr(package, cache_name, cache_name)
    course = None
    intids = component.getUtility(zope.intid.IIntIds)

    if course_intid is not cache_name:
        course = intids.queryObject(course_intid)

    if course is not None:
        return course

    # We go via the defined adapter from the catalog entry,
    # which we should have directly cached
    try:
        entry = package._v_global_legacy_catalog_entry
    except AttributeError:
        logger.warn("Consistency issue? No attribute on global package %s",
                    package)
        entry = None

    course = ICourseInstance(entry, None)
    course_intid = intids.queryId(course, None)

    setattr(package, cache_name, course_intid)
    return course

def _content_unit_to_courses(unit, include_sub_instances=True):
    # XXX JAM These heuristics aren't well tested.

    # First, try the true legacy case. This involves
    # a direct mapping between courses and a catalog entry. It may be
    # slightly more reliable, but only works for true legacy cases.
    package = find_interface(unit, ILegacyCourseConflatedContentPackageUsedAsCourse)
    if package is not None:
        result = ICourseInstance(package, None)
        if result is not None:
            return (result,)

    # Nothing true legacy. find all courses that match this pacakge
    result = []
    package = find_interface(unit, IContentPackage)
    course_catalog = component.getUtility(ICourseCatalog)
    for entry in course_catalog.iterCatalogEntries():
        instance = ICourseInstance(entry, None)
        if instance is None:
            continue
        if not include_sub_instances and ICourseSubInstance.providedBy(instance):
            continue
        try:
            packages = instance.ContentPackageBundle.ContentPackages
        except AttributeError:
            packages = (instance.legacy_content_package,)

        if package in packages:
            result.append(instance)
    return result

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit)
def _content_unit_to_course(unit):
    # get all courses, don't include sections
    courses = _content_unit_to_courses(unit, False)

    # XXX: We probably need to check and see who's enrolled
    # to find the most specific course instance to return?
    # As it stands, we promise to return only a root course,
    # not a subinstance (section)
    # XXX: FIXME: This requires a one-to-one mapping
    return courses[0] if courses else None

from .utils import is_course_instructor as is_instructor  # BWC

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit, IUser)
def _content_unit_and_user_to_course(unit, user):
    # # get all courses
    courses = _content_unit_to_courses(unit, True)
    for instance in courses or ():
        # check enrollment
        enrollments = ICourseEnrollments(instance)
        record = enrollments.get_enrollment_for_principal(user)
        if record is not None:
            return instance

        # check role
        if is_instructor(instance, user):
            return instance

    # nothing found return first course
    return courses[0] if courses else None

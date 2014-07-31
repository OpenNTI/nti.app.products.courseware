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

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance

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
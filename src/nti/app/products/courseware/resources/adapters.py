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

from zope.annotation.interfaces import IAnnotations

from nti.app.products.courseware.resources import RESOURCES

from nti.app.products.courseware.resources.filer import CourseSourceFiler

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentResource

from nti.app.products.courseware.resources.model import CourseRootFolder

from nti.base._compat import text_

from nti.contentfolder.adapters import ContainerId

from nti.contentfolder.interfaces import IContainerIdAdapter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.namedfile.constraints import FileConstraints

from nti.namedfile.interfaces import IFileConstraints

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseRootFolder)
def course_resources(context, create=True):
    result = None
    course = ICourseInstance(context)
    annotations = IAnnotations(course)
    try:
        KEY = RESOURCES
        result = annotations[KEY]
    except KeyError:
        if create:
            result = CourseRootFolder(name=RESOURCES)
            annotations[KEY] = result
            result.__name__ = KEY
            result.__parent__ = course
    if result is not None and result.creator is None:
        result.creator = SYSTEM_USER_ID
    return result
_course_resources = course_resources


@component.adapter(ICourseInstance)
@interface.implementer(ICourseRootFolder)
def _course_resources(context, create=True):
    return course_resources(context, create)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(ICourseRootFolder)
def _entry_resources(context, create=True):
    return course_resources(context, create)


def _resources_for_course_path_adapter(context, _=None):
    course = ICourseInstance(context)
    return _course_resources(course)


def _course_user_source_filer(context, user=None):
    course = ICourseInstance(context)
    return CourseSourceFiler(course, user)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseSourceFiler)
def _course_source_filer(context):
    return _course_user_source_filer(context, None)


@interface.implementer(IFileConstraints)
def _CourseFolderFileConstraints(unused_obj=None):
    result = FileConstraints()
    result.max_file_size = 104857600  # 100 MB
    return result


def _containerId_adater(context):
    course = find_interface(context, ICourseInstance, strict=False)
    entry = ICourseCatalogEntry(course, None)
    if entry is not None:
        return ContainerId(text_(entry.ntiid))
    return None


@component.adapter(ICourseContentResource)
@interface.implementer(IContainerIdAdapter)
def _course_contentresource_containerId_adapter(context):
    return _containerId_adater(context)


@component.adapter(ICourseContentFolder)
@interface.implementer(IContainerIdAdapter)
def _course_contentfolder_containerId_adapter(context):
    return _containerId_adater(context)

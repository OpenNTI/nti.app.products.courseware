#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from nti.app.base.abstract_views import get_source_filer

from nti.app.contentfolder import ASSETS_FOLDER
from nti.app.contentfolder import IMAGES_FOLDER
from nti.app.contentfolder import DOCUMENTS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler
from nti.app.products.courseware.resources.interfaces import ICourseLockedFolder

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


def get_course(context, strict=False):
    course = ICourseInstance(context, None)
    if course is None:
        course = find_interface(context, ICourseInstance, strict=strict)
    return course


def get_create_root_folder(context, name, strict=True, lock=True):
    course = get_course(context, strict=strict)
    root = ICourseRootFolder(course, None)
    if root is not None:
        if name not in root:
            result = CourseContentFolder(name=name)
            root[name] = result
        else:
            result = root[name]
        if result.creator is None:
            result.creator = SYSTEM_USER_ID
        if lock and not ICourseLockedFolder.providedBy(result):
            interface.alsoProvides(result, ICourseLockedFolder)
        return result
    return None


def get_assets_folder(context):
    return get_create_root_folder(context, ASSETS_FOLDER, strict=True)


def get_documents_folder(context):
    return get_create_root_folder(context, DOCUMENTS_FOLDER, strict=True)


def get_images_folder(context):
    return get_create_root_folder(context, IMAGES_FOLDER, strict=True)


def get_course_filer(context, user=None, strict=False):
    course = get_course(context, strict=strict)
    return get_source_filer(course, user, ICourseSourceFiler)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.base.abstract_views import get_source_filer

from nti.app.contentfile.view_mixins import is_oid_external_link
from nti.app.contentfile.view_mixins import to_external_download_oid_href
from nti.app.contentfile.view_mixins import get_file_from_oid_external_link

from nti.app.contentfolder.utils import is_cf_io_href
from nti.app.contentfolder.utils import to_external_cf_io_href
from nti.app.contentfolder.utils import get_file_from_cf_io_url

from nti.app.products.courseware import ASSETS_FOLDER
from nti.app.products.courseware import IMAGES_FOLDER
from nti.app.products.courseware import DOCUMENTS_FOLDER

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler
from nti.app.products.courseware.resources.interfaces import ICourseLockedFolder

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.traversal.traversal import find_interface


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


def is_internal_file_link(link):
    return is_oid_external_link(link) or is_cf_io_href(link)


def get_file_from_external_link(link):
    if is_oid_external_link(link):
        return get_file_from_oid_external_link(link)
    elif is_cf_io_href(link):
        return get_file_from_cf_io_url(link)
    return None


def to_external_file_link(context, oid=True):
    if oid:
        return to_external_download_oid_href(context)
    return to_external_cf_io_href(context)

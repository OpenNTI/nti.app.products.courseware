#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
from mimetypes import guess_type

from plone.namedfile.utils import getImageInfo

from zope import interface
from zope import lifecycleevent

from nti.app.contentfile import transfer_data

from nti.app.contentfolder import ASSETS_FOLDER

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import to_external_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.app.contentfolder.utils import get_unique_file_name

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentImage
from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.app.products.courseware.resources.utils import get_assets_folder
from nti.app.products.courseware.resources.utils import get_images_folder
from nti.app.products.courseware.resources.utils import get_documents_folder

from nti.base._compat import text_

from nti.base.interfaces import DEFAULT_CONTENT_TYPE

from nti.contentfolder.utils import mkdirs
from nti.contentfolder.utils import traverse
from nti.contentfolder.utils import TraversalException

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_ID

from nti.traversal.traversal import find_interface


def get_namedfile_factory(source):
    contentType = getattr(source, 'contentType', None)
    if contentType:
        factory = CourseContentFile
    else:
        contentType, _, _ = getImageInfo(source)
        source.seek(0)  # reset
        factory = CourseContentFile if contentType else CourseContentImage
    contentType = contentType or text_(DEFAULT_CONTENT_TYPE)
    return factory, contentType


def get_namedfile_from_source(source, filename, name=None):
    factory, contentType = get_namedfile_factory(source)
    result = factory()
    result.filename = filename
    transfer_data(source, result)
    result.contentType = result.contentType or contentType
    if name and filename != name:
        result.name = name
    return result


def is_image(key, contentType=None):
    result = (guess_type(key.lower())[0] or '').startswith('image/') \
          or (contentType or '').startswith('image/')
    return result


@interface.implementer(ICourseSourceFiler)
class CourseSourceFiler(object):

    default_bucket = None

    def __init__(self, context=None, user=None, oid=False):
        self.oid = oid
        self.user = user
        self.course = ICourseInstance(context)

    @property
    def username(self):
        return getattr(self.user, 'username', None)

    @property
    def root(self):
        return ICourseRootFolder(self.course)

    @property
    def assets(self):
        return get_assets_folder(self.course)

    @property
    def images(self):
        return get_images_folder(self.course)

    @property
    def documents(self):
        return get_documents_folder(self.course)

    def get_create_folders(self, parent, name):
        def builder():
            result = CourseContentFolder()
            result.creator = self.username or SYSTEM_USER_ID
            return result
        result = mkdirs(parent, name, factory=builder)
        return result
    get_create_folder = get_create_folders

    def save(self, key, source, contentType=None, bucket=None,
             overwrite=False, structure=False, **kwargs):
        username = self.username
        context = kwargs.get('context')
        bucket = bucket or self.default_bucket
        if structure:
            bucket = self.images if is_image(key, contentType) else self.documents
        elif bucket == ASSETS_FOLDER:  # legacy
            bucket = self.assets
        elif bucket:
            bucket = self.get_create_folders(self.root, bucket)
        else:
            bucket = self.root

        modified = False
        namedfile = None
        filename = text_(key)
        if overwrite:
            if filename in bucket:
                namedfile = bucket[filename]
        else:
            filename = get_unique_file_name(filename, bucket)

        if namedfile is None:
            namedfile = get_namedfile_from_source(source, filename)
            namedfile.creator = username or SYSTEM_USER_ID  # set creator
            bucket.add(namedfile)
        else:
            modified = True
            transfer_data(source, namedfile)

        if contentType:
            namedfile.contentType = contentType

        if context is not None:
            modified = True
            namedfile.add_association(context)
        if modified:
            lifecycleevent.modified(namedfile)

        # return external link
        result = self.get_external_link(namedfile)
        return result

    def get(self, key, bucket=None):
        result = None
        bucket = bucket or self.default_bucket
        if is_internal_file_link(key):
            result = get_file_from_external_link(key)
            if result is not None:
                course = find_interface(result, ICourseInstance, strict=False)
                if course is not self.course:  # not the same course
                    result = None
        elif bucket:
            context = traverse(self.root, bucket)
            if context is not None and key in context:
                result = context[key]
        else:
            path, key = os.path.split(key)
            context = traverse(self.root, path)
            if context is not None and key in context:
                result = context[key]
        return result

    def remove(self, key, bucket=None):
        bucket = bucket or self.default_bucket
        try:
            result = self.get(key, bucket=bucket)
            if result is not None:
                parent = result.__parent__
                parent.remove(result)
                return True
        except TraversalException:
            pass
        return False

    def contains(self, key, bucket=None):
        bucket = bucket or self.default_bucket
        if is_internal_file_link(key):
            result = self.get(key) is not None
        else:
            try:
                context = traverse(self.root, bucket) if bucket else self.root
                result = key in context
            except TraversalException:
                result = False
        return result

    def list(self, bucket=None):
        bucket = bucket or self.default_bucket
        context = traverse(self.root, bucket) if bucket else self.root
        path = context.path or u'/'
        result = tuple(os.path.join(path, name) for name in context.keys())
        return result

    def is_bucket(self, bucket):
        try:
            context = traverse(self.root, bucket) if bucket else self.root
            result = ICourseContentFolder.providedBy(context) \
                or ICourseRootFolder.providedBy(context)
        except TraversalException:
            result = False
        return result
    isBucket = is_bucket

    def key_name(self, identifier):
        if is_internal_file_link(identifier):
            result = self.get(identifier)
            result = result.__name__ if result is not None else None
        else:
            result = os.path.split(identifier)[1]
        return result
    keyName = key_name

    def get_external_link(self, item):
        return to_external_file_link(item, self.oid)
    to_external_link = get_external_link

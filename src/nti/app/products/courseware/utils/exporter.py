#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import six

from zope import component
from zope import interface

from zope.interface.interfaces import IMethod

from zope.intid.interfaces import IIntIds

from nti.app.contentfolder import ASSETS_FOLDER
from nti.app.contentfolder import IMAGES_FOLDER
from nti.app.contentfolder import DOCUMENTS_FOLDER

from nti.app.contentfolder.resources import is_internal_file_link
from nti.app.contentfolder.resources import get_file_from_external_link

from nti.app.products.courseware.utils import EXPORT_HASH_KEY
from nti.app.products.courseware.utils import COURSE_META_NAME

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter
from nti.contenttypes.courses.interfaces import NTI_COURSE_FILE_SCHEME

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

MIMETYPE = StandardExternalFields.MIMETYPE

logger = __import__('logging').getLogger(__name__)


def save_resource_to_filer(reference, filer, overwrite=True, context=None):
    if isinstance(reference, six.string_types):
        resource = get_file_from_external_link(reference)
    if resource is None:
        return None
    contentType = resource.contentType
    if hasattr(resource, 'path'):
        path = resource.path
        # remove resource name
        path = os.path.split(path)[0] if path else ''
        path = path[1:] if path.startswith('/') else path
        if not path:
            path = ASSETS_FOLDER
        elif    not path.startswith(IMAGES_FOLDER) \
            and not path.startswith(DOCUMENTS_FOLDER) \
            and not path.startswith(ASSETS_FOLDER):
            path = os.path.join(ASSETS_FOLDER, path)
    else:
        path = ASSETS_FOLDER
    # save resource
    filer.save(resource.name,
               resource,
               bucket=path,
               context=context,
               overwrite=overwrite,
               contentType=contentType)
    # get course file scheme
    internal = NTI_COURSE_FILE_SCHEME + path + "/" + resource.name
    return internal


def save_resources_to_filer(provided, obj, filer, ext_obj=None):
    """
    parse the provided interface field and look for internal resources to
    be saved in the specified filer
    """
    result = {}
    for name in provided:
        if name.startswith('_'):
            continue
        value = getattr(obj, name, None)
        if      value is not None \
            and not IMethod.providedBy(value) \
            and isinstance(value, six.string_types) \
            and is_internal_file_link(value):
            # get resource
            internal = save_resource_to_filer(value, filer, True, obj)
            if internal is None:
                continue
            logger.debug("%s was saved as %s", value, internal)
            result[name] = internal
            if ext_obj is not None:
                ext_obj[name] = internal
    return result


@interface.implementer(ICourseSectionExporter)
class CourseMetaInfoExporter(BaseSectionExporter):
    
    def _get_export_hash(self, course, salt):
        # This should ensure we only ever import this course/salt combo once
        # per environment.
        intids = component.queryUtility(IIntIds)
        course_intid = intids.getId(course)
        return '%s_%s' % (course_intid, salt)
    
    def export(self, context, filer, backup=True, salt=None):
        filer.default_bucket = None
        course = ICourseInstance(context)
        if ICourseSubInstance.providedBy(course):
            return
        export_hash = self._get_export_hash(course, salt)
        data = {
            MIMETYPE: course.mime_type,
            EXPORT_HASH_KEY: export_hash
        }
        ext_obj = to_external_object(data, decorate=False)
        source = self.dump(ext_obj)
        filer.save(COURSE_META_NAME, source,
                   contentType="application/json",
                   overwrite=True)

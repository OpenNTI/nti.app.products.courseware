#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentImage

from nti.contentfile.datastructures import BaseFactory
from nti.contentfile.datastructures import ContentFileObjectIO
from nti.contentfile.datastructures import ContentImageObjectIO

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseContentFile)
class CourseContentFileObjectIO(ContentFileObjectIO):

    _ext_iface_upper_bound = ICourseContentFile

    def _ext_mimeType(self, _):
        return 'application/vnd.nextthought.courseware.contentfile'


@component.adapter(ICourseContentImage)
class CourseContentImageObjectIO(ContentImageObjectIO):

    _ext_iface_upper_bound = ICourseContentImage

    def _ext_mimeType(self, _):
        return 'application/vnd.nextthought.courseware.contentimage'


def CourseContentFileFactory(ext_obj):
    return BaseFactory(ext_obj, CourseContentFile, CourseContentFile)


def CourseContentImageFactory(ext_obj):
    return BaseFactory(ext_obj, CourseContentImage, CourseContentImage)

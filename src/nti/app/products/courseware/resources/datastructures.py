#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from nti.app.products.courseware.resources.interfaces import ICourseContentFile

from nti.app.products.courseware.resources.model import CourseContentFile

from nti.contentfile.datastructures import BaseFactory
from nti.contentfile.datastructures import ContentFileObjectIO

@component.adapter(ICourseContentFile)
class CourseContentFileObjectIO(ContentFileObjectIO):

    _ext_iface_upper_bound = ICourseContentFile

    def _ext_mimeType(self, obj):
        return u'application/vnd.nextthought.courseware.contentfile'

def CourseContentFileFactory(ext_obj):
    result = BaseFactory(ext_obj, CourseContentFile, CourseContentFile)
    return  result

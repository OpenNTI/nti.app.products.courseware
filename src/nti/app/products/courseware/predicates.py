#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentUnitAssociations

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.traversal.traversal import find_interface


@component.adapter(IContentUnit)
@interface.implementer(IContentUnitAssociations)
class _CourseContentUnitAssociations(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def associations(self, context):
        result = []
        package = find_interface(context, IContentPackage, strict=False)
        if package is not None:
            courses = get_courses_for_packages(packages=(package.ntiid,))
            for course in courses or ():
                # favor catalog entries
                entry = ICourseCatalogEntry(course, None)
                if entry is not None:
                    result.append(entry)
                else:
                    result.append(course)
        return result or ()

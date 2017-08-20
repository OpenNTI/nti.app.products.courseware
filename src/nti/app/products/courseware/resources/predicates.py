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

from zope.container.interfaces import IContentContainer

from nti.app.products.courseware.resources.adapters import course_resources

from nti.appserver.pyramid_authorization import has_permission

from nti.contentfolder.interfaces import IContentResources

from nti.contenttypes.courses.predicates import course_collector

from nti.contenttypes.courses.utils import is_enrolled_in_hierarchy

from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ISystemUserPrincipal

from nti.dataserver.metadata.predicates import BasePrincipalObjects


def is_instructor_or_editor(course, user):
    return is_course_instructor_or_editor(course, user) \
        or has_permission(ACT_CONTENT_EDIT, course)


def folder_objects(folder):
    result = []
    for item in folder.values():
        if IContentContainer.providedBy(item):
            result.append(item)
            result.extend(folder_objects(item))
        else:
            result.append(item)
    return result


def course_files(course):
    root = course_resources(course, False)
    if root:
        for item in folder_objects(root):
            yield item


@component.adapter(IUser)
class _CourseFilesMixin(BasePrincipalObjects):

    def folder_objects(self, folder):
        return folder_objects(folder)

    def course_files(self, course):
        return course_files(course)


@component.adapter(IUser)
class _CourseUserFileObjects(_CourseFilesMixin):

    def iter_objects(self):
        result = set()
        for course in course_collector():
            if     is_instructor_or_editor(course, self.user) \
                or is_enrolled_in_hierarchy(course, self.user):
                for item in self.course_files(course):
                    if item not in result and self.creator(item) == self.username:
                        result.add(item)
        return result


@component.adapter(ISystemUserPrincipal)
class _CourseSystemFileObjects(_CourseFilesMixin):

    def iter_objects(self):
        result = []
        for course in course_collector():
            for item in self.course_files(course):
                if self.is_system_username(self.creator(item)):
                    result.append(item)
        return result


@interface.implementer(IContentResources)
class _CatalogContentResources(object):
    
    __slots__ = ()

    def __init__(self, *args):
        pass

    def iter_objects(self):
        for course in course_collector():
            for item in course_files(course):
                yield item

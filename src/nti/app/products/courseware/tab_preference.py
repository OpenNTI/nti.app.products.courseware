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

from zope.container.contained import Contained

from nti.app.products.courseware.interfaces import ICourseTabConfigurationUtility

from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseTabPreferences

from nti.contenttypes.courses.utils import get_parent_course

from nti.contenttypes.courses.tab_preference import CourseTabPreferencesFactory

from nti.dataserver.authorization import is_admin

from nti.externalization.persistence import NoPickle

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseTabConfigurationUtility)
class DefaultCourseTabConfigurationUtility(object):

    def can_edit_tabs(self, user, unused_course=None):
        return is_admin(user)


@NoPickle
@interface.implementer(ICourseTabPreferences)
class SectioninstanceCourseTabPreferences(Contained):

    def __init__(self, section_prefs, parent_prefs):
        self.section_prefs = section_prefs
        self.parent_prefs = parent_prefs

    def update_names(self, names):
        self.section_prefs.update_names(names)

    def update_order(self, order):
        self.section_prefs.update_order(order)

    def clear(self):
        self.section_prefs.clear()

    @property
    def creator(self):
        return self.section_prefs.creator

    @property
    def names(self):
        _names = self.parent_prefs.names
        _names.update(self.section_prefs.names)
        return _names

    @property
    def order(self):
        return self.section_prefs.order or self.parent_prefs.order


@component.adapter(ICourseSubInstance)
@interface.implementer(ICourseTabPreferences)
def _section_instance_course_tab_preferences(course):
    section_prefs = CourseTabPreferencesFactory(course)
    parent_course = get_parent_course(course)
    if parent_course.Outline != course.Outline:
        return section_prefs

    parent_prefs = ICourseTabPreferences(parent_course)
    return SectioninstanceCourseTabPreferences(section_prefs,
                                               parent_prefs)

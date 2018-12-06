#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar

from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IObjectAddedEvent)
def _on_course_added(course, unused_event=None):
    ICourseCalendar(course)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, unused_event=None):
    calendar = ICourseCalendar(course, None)
    if calendar is not None:
        calendar.clear()

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.container.contained import Contained

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.contenttypes.calendar.model import Calendar
from nti.contenttypes.calendar.model import CalendarEvent

from nti.dataserver.authorization_acl import acl_from_aces

from nti.property.property import LazyOnClass

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCalendar)
class CourseCalendar(Calendar, Contained):

    __external_class_name__ = "CourseCalendar"
    mimeType = mime_type = "application/vnd.nextthought.courseware.coursecalendar"


@interface.implementer(ICourseCalendarEvent)
class CourseCalendarEvent(CalendarEvent):

    __external_class_name__ = "CourseCalendarEvent"
    mimeType = mime_type = "application/vnd.nextthought.courseware.coursecalendarevent"

    @LazyOnClass
    def __acl__(self):
        # If we don't have this, it would derive one from ICreated, rather than its parent.
        return acl_from_aces([])

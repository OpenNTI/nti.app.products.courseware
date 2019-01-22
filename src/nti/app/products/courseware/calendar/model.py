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

from zope.cachedescriptors.property import readproperty

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.contenttypes.calendar.model import Calendar
from nti.contenttypes.calendar.model import CalendarEvent

from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import IUser

from nti.dataserver.sharing import AbstractReadableSharedMixin

from nti.dataserver.users import User

from nti.property.property import LazyOnClass

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseCalendar)
class CourseCalendar(Calendar, Contained):

    __external_class_name__ = "CourseCalendar"
    mimeType = mime_type = "application/vnd.nextthought.courseware.coursecalendar"

    @readproperty
    def title(self):
        return getattr(self.__parent__, 'title', None) or u''


@interface.implementer(ICourseCalendarEvent)
class CourseCalendarEvent(CalendarEvent, AbstractReadableSharedMixin):

    __external_class_name__ = "CourseCalendarEvent"
    mimeType = mime_type = "application/vnd.nextthought.courseware.coursecalendarevent"

    @LazyOnClass
    def __acl__(self):
        # If we don't have this, it would derive one from ICreated, rather than its parent.
        return acl_from_aces([])

    @property
    def sharingTargets(self):
        course = ICourseInstance(self, None)
        if course is not None:
            scope = course.SharingScopes.get(ES_PUBLIC)
            return (scope, ) if scope is not None else ()
        return ()

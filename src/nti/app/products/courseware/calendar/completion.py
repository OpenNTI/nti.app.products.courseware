#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from zope import component
from zope import interface

from zope.lifecycleevent import IObjectAddedEvent

from zope.lifecycleevent import IObjectRemovedEvent

from zope.security.interfaces import IPrincipal

from nti.contenttypes.calendar.interfaces import ICalendarEvent
from nti.contenttypes.calendar.interfaces import ICalendarEventAttendanceContainer
from nti.contenttypes.calendar.interfaces import IUserCalendarEventAttendance

from nti.contenttypes.completion.completion import CompletedItem

from nti.contenttypes.completion.interfaces import ICompletableItemCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.completion.policies import AbstractCompletableItemCompletionPolicy

from nti.contenttypes.completion.progress import Progress

from nti.contenttypes.completion.utils import remove_completion
from nti.contenttypes.completion.utils import update_completion

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IUser

from nti.dataserver.users import User

from nti.externalization.persistence import NoPickle


@NoPickle
@component.adapter(ICalendarEvent, ICourseInstance)
@interface.implementer(ICompletableItemCompletionPolicy)
class CalendarEventCompletionPolicy(AbstractCompletableItemCompletionPolicy):

    def __init__(self, event, course):
        self.event = event
        self.course = course

    def is_complete(self, progress):
        result = None
        if progress is not None and progress.HasProgress:
            result = CompletedItem(Item=progress.Item,
                                   Principal=progress.User,
                                   CompletedDate=progress.LastModified)
        return result


@component.adapter(IUser, ICalendarEvent, ICourseInstance)
@interface.implementer(IProgress)
def _event_progress(user, event, course):
    """
    Fetch the :class:`IProgress` for this user, event, course.
    """
    progress = None

    attendance_container = ICalendarEventAttendanceContainer(event, None)
    user_attendance = attendance_container.get(IPrincipal(user).id)

    if user_attendance:
        progress = Progress(NTIID=event.ntiid,
                            AbsoluteProgress=None,
                            MaxPossibleProgress=None,
                            LastModified=user_attendance.created,
                            User=user,
                            Item=event,
                            CompletionContext=course,
                            HasProgress=True)
    return progress


@component.adapter(IUserCalendarEventAttendance, IObjectAddedEvent)
def on_attendance_recorded(user_attendance, _event):
    event = ICalendarEvent(user_attendance)
    course = ICourseInstance(event, None)
    if course:
        user = User.get_user(user_attendance.Username)
        update_completion(event, event.ntiid, user, course)


@component.adapter(IUserCalendarEventAttendance, IObjectRemovedEvent)
def on_attendance_removed(user_attendance, _event):
    event = ICalendarEvent(user_attendance)
    course = ICourseInstance(event, None)
    if course:
        user = User.get_user(user_attendance.Username)
        remove_completion(event, event.ntiid, user, course)

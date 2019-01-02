#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from zope import component

from zope.event import notify

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from zope.annotation.interfaces import IAnnotations

from zope.lifecycleevent import ObjectModifiedEvent

from nti.app.products.courseware.calendar.interfaces import ICourseCalendar
from nti.app.products.courseware.calendar.interfaces import ICourseCalendarEvent

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.containers.containers import CaseInsensitiveLastModifiedBTreeContainer

from nti.contenttypes.calendar.processing import queue_add
from nti.contenttypes.calendar.processing import queue_modified

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.dataserver.activitystream_change import Change

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User


logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IObjectAddedEvent)
def _on_course_added(course, unused_event=None):
    ICourseCalendar(course)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, unused_event=None):
    calendar = ICourseCalendar(course, None)
    if calendar is not None:
        calendar.clear()


@component.adapter(ICourseCalendarEvent, IObjectAddedEvent)
def _on_course_calendar_event_added(calendar_event, unused_event):
    queue_add(calendar_event)


@component.adapter(ICourseCalendarEvent, IObjectModifiedEvent)
def _on_course_calendar_event_modified(calendar_event, unused_event):
    queue_modified(calendar_event)


_CHANGE_KEY = u'nti.app.products.courseware.subscribers.CALENDAR_EVENT_CHANGE_KEY'


def _get_calendar_change_storage(calendar):
    annotes = IAnnotations(calendar)
    changes = annotes.get(_CHANGE_KEY)
    if changes is None:
        changes = CaseInsensitiveLastModifiedBTreeContainer()
        changes.__name__ = _CHANGE_KEY
        changes.__parent__ = calendar
        annotes[_CHANGE_KEY] = changes
    return annotes[_CHANGE_KEY]


def _get_user(user):
    if not IUser.providedBy(user) and user:
        result = User.get_user(user)
    else:
        result = user
    return user if result is None else user


def _enrolled_principals(calendar_event):
    course = ICourseInstance(calendar_event)
    enrollments = ICourseEnrollments(course)
    users = [User.get_user(x) for x in enrollments.iter_principals()]
    return [x.username for x in users if IUser.providedBy(x)]


def _do_store_event_created(calendar_event):
    calendar = ICourseCalendar(calendar_event, None)
    if calendar is None:
        return
    storage = _get_calendar_change_storage(calendar)
    if calendar_event.ntiid in storage:
        # should we also update the sharedWith here?
        change = storage[calendar_event.ntiid]
        change.updateLastMod()
        notify(ObjectModifiedEvent(change))
        return

    change = Change(Change.CREATED, calendar_event)
    now = time.time()
    change.lastModified = now
    change.createdTime = now
    if calendar_event.creator is not None:
        change.creator = _get_user(calendar_event.creator) if calendar_event.creator != SYSTEM_USER_NAME \
                            else SYSTEM_USER_NAME
    else:
        change.creator = SYSTEM_USER_NAME
        calendar_event.creator = SYSTEM_USER_NAME

    # what about if a student drop the course?
    change.sharedWith = _enrolled_principals(calendar_event)
    change.__copy_object_acl__ = True

    # Now store it, firing events to index, etc. Remember this
    # only happens if the name and parent aren't already
    # set (which they will be because they were copied from calendar_event)
    del change.__name__
    del change.__parent__

    # Define it as top-level content for indexing purposes
    change.__is_toplevel_content__ = True
    storage[calendar_event.ntiid] = change
    assert change.__parent__ is _get_calendar_change_storage(calendar)
    assert change.__name__ == calendar_event.ntiid
    return change


@component.adapter(ICourseCalendarEvent, IObjectModifiedEvent)
@component.adapter(ICourseCalendarEvent, IObjectAddedEvent)
def _course_calendar_event_created_event(calendar_event, unused_event):
    _do_store_event_created(calendar_event)


@component.adapter(ICourseCalendarEvent, IObjectRemovedEvent)
def _remove_course_calendar_event(calendar_event, unused_event=None):
    try:
        calendar = ICourseCalendar(calendar_event)
        storage = _get_calendar_change_storage(calendar)
        del storage[calendar_event.ntiid]
    except KeyError:
        pass

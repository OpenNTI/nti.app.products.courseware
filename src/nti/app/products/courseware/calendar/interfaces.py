#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.container.constraints import contains

from zope.location.interfaces import IContained

from nti.contenttypes.calendar.interfaces import ICalendar
from nti.contenttypes.calendar.interfaces import ICalendarEvent

from nti.zope_catalog.interfaces import INoAutoIndexEver


class ICourseCalendarEvent(ICalendarEvent):
    """
    A calendar event that should be within the course context.
    """


class ICourseCalendar(ICalendar, IContained):
    """
    A calendar that should be annotated on the course instance object.
    """
    contains(ICourseCalendarEvent)
    __setitem__.__doc__ = None


class ICourseCalendarDynamicEvent(ICourseCalendarEvent, INoAutoIndexEver):
    """
    A calendar event that should be produced dynamically, and not persistent.
    """


class ICourseCalendarDynamicEventProvider(interface.Interface):
    """
    An intended subscriber provider of possible :class:`ICourseCalendarDynamicEvent` objects
    for a :class:`IUser` and :class:`ICourseInstance`.
    """

    def iter_events():
        """
        A generator of :class:`ICourseCalendarDynamicEvent` objects.
        """

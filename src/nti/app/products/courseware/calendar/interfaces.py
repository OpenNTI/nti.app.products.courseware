#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.container.constraints import contains

from zope.location.interfaces import IContained

from nti.contenttypes.calendar.interfaces import ICalendar
from nti.contenttypes.calendar.interfaces import ICalendarEvent


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


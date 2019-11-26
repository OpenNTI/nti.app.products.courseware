#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope import component
from zope import interface

from zope.event import notify

from nti.contenttypes.completion.subscribers import completion_context_deleted_event

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import ICompletionContextCompletedItem
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import CourseCompletedEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_deleted(course, unused_event=None):
    # clear containers. sections have their own
    completion_context_deleted_event(course)


@component.adapter(ICourseInstance, IUserProgressUpdatedEvent)
def _course_progress_updated(course, event):
    """
    The user has successfully completed a required item. If the user course
    progress moves from a state of incomplete to (successfully) complete,
    broadcast an appropriate event.

    Since we are storing course completion persistently, this means this
    event will only be fired once, upon the first successful completion.

    This object is not used when querying course completion state. To do
    that correctly, we'd have to determine how to handle shifting
    requirements.
    """
    user = event.user
    principal_container = component.queryMultiAdapter((user, course),
                                                      IPrincipalCompletedItemContainer)
    # If this has already been completed successfully, take no action.
    if     principal_container \
       and principal_container.ContextCompletedItem is not None\
       and principal_container.ContextCompletedItem.Success:
        return

    policy = ICompletionContextCompletionPolicy(course, None)
    if not policy:
        return

    progress = component.queryMultiAdapter((user, course),
                                           IProgress)
    if      progress.CompletedItem \
        and progress.CompletedItem.Success:
        # Newly successful completion, store and notify
        course_completed_item = progress.CompletedItem
        interface.alsoProvides(course_completed_item, ICompletionContextCompletedItem)
        course_completed_item.__parent__ = principal_container
        principal_container.ContextCompletedItem = course_completed_item
        notify(CourseCompletedEvent(course, user))

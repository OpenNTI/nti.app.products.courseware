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

from nti.contenttypes.completion.subscribers import completion_context_deleted_event

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

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
    """
    user = event.user
    entry = ICourseCatalogEntry(course)
    principal_container = component.queryMultiAdapter((user, course),
                                                      IPrincipalCompletedItemContainer)
    # If this has already been completed successfully, take no action.
    if     principal_container \
       and entry.ntiid in principal_container \
       and principal_container[entry.ntiid].Success:
        return

    policy = ICompletionContextCompletionPolicy(course, None)
    if not policy:
        return

    progress = component.queryMultiAdapter((user, course),
                                           IProgress)
    if      progress.CompletedItem \
        and progress.CompletedItem.Success:
        # Ok, the course is currently complete; check the -1 case.
        # XXX: If we stored completion in our container, we could use that
        # to check the previous state instead.
        if progress.AbsoluteProgress:
            progress.AbsoluteProgress -= 1
            completed_item = policy.is_complete(progress)
            if     not completed_item \
                or not completed_item.Success:
                notify()

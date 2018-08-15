#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component

from nti.contenttypes.completion.subscribers import completion_context_deleted_event

from nti.contenttypes.courses.interfaces import ICourseInstance

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IBeforeIdRemovedEvent)
def _on_course_deleted(course, unused_event):
    # clear containers. sections have their own
    completion_context_deleted_event(course)

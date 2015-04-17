#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion 

@component.adapter(ICourseDiscussion, IObjectAddedEvent)
def _discussions_added(record, event):
    pass

@component.adapter(ICourseDiscussion, IObjectModifiedEvent)
def _discussions_modified(record, event):
    pass

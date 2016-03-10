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
from zope.lifecycleevent import IObjectRemovedEvent

from nti.app.products.courseware.resources.adapters import course_resources

from nti.contenttypes.courses.interfaces import ICourseInstance

@component.adapter(ICourseInstance, IObjectAddedEvent)
def _on_course_added(course, event):
	course_resources(course)

@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_removed(course, event):
	root = course_resources(course, False)
	if root is not None:
		root.clear()

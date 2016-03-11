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

from nti.app.products.courseware.discussions import create_topics
from nti.app.products.courseware.discussions import auto_create_forums
from nti.app.products.courseware.discussions import update_course_forums

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseRolesSynchronized
from nti.contenttypes.courses.interfaces import ICatalogEntrySynchronized

@component.adapter(ICourseDiscussion, IObjectAddedEvent)
def _discussions_added(record, event):
	if auto_create_forums(record):
		create_topics(record)

@component.adapter(ICourseDiscussion, IObjectModifiedEvent)
def _discussions_modified(record, event):
	if auto_create_forums(record):
		create_topics(record)

@component.adapter(ICourseCatalogEntry, ICatalogEntrySynchronized)
def _catalog_entry_synchronized(entry, event):
	course = ICourseInstance(entry, None)
	if course is not None and auto_create_forums(course):
		update_course_forums(course)

@component.adapter(ICourseInstance, ICourseRolesSynchronized)
def _course_roles_synchronized(course, event):
	if course is not None and auto_create_forums(course):
		update_course_forums(course)

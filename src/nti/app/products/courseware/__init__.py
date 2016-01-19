#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.app.products.courseware')

#: Folder for storing course assets
ASSETS_FOLDER = 'assets'

USER_ENROLLMENT_LAST_MODIFIED_KEY = 'nti.app.products.courseware.UserEnrollmentLastModified'

VIEW_CONTENTS = 'contents'
VIEW_COURSE_MAIL = 'Mail'
VIEW_CLASSMATES = 'Classmates'
VIEW_COURSE_CLASSMATES = 'Classmates'
VIEW_COURSE_ACTIVITY = 'CourseActivity'
VIEW_CATALOG_ENTRY = 'CourseCatalogEntry'
VIEW_COURSE_DISCUSSIONS = 'CourseDiscussions'
VIEW_COURSE_RECURSIVE = 'CourseRecursiveStream'
VIEW_COURSE_ENROLLMENT_ROSTER = 'CourseEnrollmentRoster'
VIEW_COURSE_RECURSIVE_BUCKET = 'CourseRecursiveStreamByBucket'

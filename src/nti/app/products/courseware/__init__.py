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

#: Folder for storing course documents
DOCUMENTS_FOLDER = 'Documents'

#: Folder for storing course images
IMAGES_FOLDER = 'Images'

#: User enrollment last mod annotation key
USER_ENROLLMENT_LAST_MODIFIED_KEY = 'nti.app.products.courseware.UserEnrollmentLastModified'

SEND_COURSE_INVITATIONS = 'SendCourseInvitations'
CHECK_COURSE_INVITATIONS_CSV = 'CheckCourseInvitationsCSV'

ACCEPT_COURSE_INVITATION = 'accept-course-invitation'
ACCEPT_COURSE_INVITATIONS = 'accept-course-invitations'

VIEW_CONTENTS = 'contents'
VIEW_COURSE_MAIL = 'Mail'
VIEW_EXPORT_COURSE = 'Export'
VIEW_IMPORT_COURSE = 'Import'
VIEW_CLASSMATES = 'Classmates'
VIEW_COURSE_CLASSMATES = 'Classmates'
VIEW_COURSE_ACTIVITY = 'CourseActivity'
VIEW_CATALOG_ENTRY = 'CourseCatalogEntry'
VIEW_COURSE_DISCUSSIONS = 'CourseDiscussions'
VIEW_COURSE_ACCESS_TOKENS = 'CourseAccessTokens'
VIEW_COURSE_RECURSIVE = 'CourseRecursiveStream'
VIEW_RECURSIVE_AUDIT_LOG = 'recursive_audit_log'
VIEW_COURSE_LOCKED_OBJECTS = 'SyncLockedObjects'
VIEW_RECURSIVE_TX_HISTORY = 'RecursiveTransactionHistory'
VIEW_COURSE_ENROLLMENT_ROSTER = 'CourseEnrollmentRoster'
VIEW_COURSE_RECURSIVE_BUCKET = 'CourseRecursiveStreamByBucket'

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory(__name__)

#: User enrollment last mod annotation key
USER_ENROLLMENT_LAST_MODIFIED_KEY = 'nti.app.products.courseware.UserEnrollmentLastModified'

VIEW_ENABLE_INVITATION = 'EnableCourseInvitation'
SEND_COURSE_INVITATIONS = 'SendCourseInvitations'
VIEW_CREATE_COURSE_INVITATION = 'CreateCourseInvitation'
CHECK_COURSE_INVITATIONS_CSV = 'CheckCourseInvitationsCSV'

ACCEPT_COURSE_INVITATION = 'accept-course-invitation'
ACCEPT_COURSE_INVITATIONS = 'accept-course-invitations'

VIEW_CONTENTS = 'contents'
VIEW_COURSE_MAIL = 'Mail'
VIEW_COURSE_BY_TAG = 'ByTag'
VIEW_RESOURCES = 'resources'
VIEW_CLASSMATES = 'Classmates'
VIEW_CURRENT_COURSES = "Current"
VIEW_ARCHIVED_COURSES = "Archived"
VIEW_UPCOMING_COURSES = "Upcoming"
VIEW_COURSE_FAVORITES = 'Favorites'
VIEW_LESSONS_CONTAINERS = 'Lessons'
VIEW_COURSE_CLASSMATES = 'Classmates'
VIEW_COURSE_ACTIVITY = 'CourseActivity'
VIEW_USER_ENROLLMENTS = 'UserEnrollments'
VIEW_ENROLLMENT_OPTIONS = 'EnrollmentOptions'
VIEW_CATALOG_ENTRY = 'CourseCatalogEntry'
VIEW_ENROLLED_WINDOWED = 'WindowedEnrolled'
VIEW_COURSE_DISCUSSIONS = 'CourseDiscussions'
VIEW_COURSE_RECURSIVE = 'CourseRecursiveStream'
VIEW_ALL_COURSES_WINDOWED = 'WindowedAllCourses'
VIEW_COURSE_ACCESS_TOKENS = 'CourseAccessTokens'
VIEW_COURSE_LOCKED_OBJECTS = 'SyncLockedObjects'
VIEW_RECURSIVE_AUDIT_LOG = 'recursive_audit_log'
VIEW_ADMINISTERED_WINDOWED = 'WindowedAdministered'
VIEW_USER_COURSE_ACCESS = 'UserCoursePreferredAccess'
VIEW_COURSE_CATALOG_FAMILIES = 'CourseCatalogFamilies'
VIEW_ALL_ENTRIES_WINDOWED = 'WindowedAllCatalogEntries'
VIEW_COURSE_ENROLLMENT_ROSTER = 'CourseEnrollmentRoster'
VIEW_RECURSIVE_TX_HISTORY = 'RecursiveTransactionHistory'
VIEW_COURSE_RECURSIVE_BUCKET = 'CourseRecursiveStreamByBucket'
VIEW_CERTIFICATE = 'Certificate'

VIEW_UPDATE_WEBINAR_PROGRESS = 'UpdateWebinarProgress'
VIEW_ALL_SITE_UPDATE_WEBINAR_PROGRESS = 'UpdateAllSiteWebinarProgress'

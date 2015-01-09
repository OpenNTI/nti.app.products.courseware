#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

VIEW_CONTENTS = 'contents'

VIEW_CATALOG_ENTRY = 'CourseCatalogEntry'
VIEW_COURSE_ENROLLMENT_ROSTER = 'CourseEnrollmentRoster'
VIEW_COURSE_ACTIVITY = 'CourseActivity'
VIEW_COURSE_RECURSIVE = 'RecursiveStream'

import zope.i18nmessageid
MessageFactory = zope.i18nmessageid.MessageFactory('nti.app.products.courseware')

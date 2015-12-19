#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from .. import MessageFactory

from zope import interface
from zope.container.contained import Contained
from zope.traversing.interfaces import IPathAdapter

from .. import ASSETS_FOLDER
from .. import VIEW_CONTENTS
from .. import VIEW_COURSE_MAIL
from .. import VIEW_CATALOG_ENTRY
from .. import VIEW_COURSE_ACTIVITY
from .. import VIEW_COURSE_RECURSIVE
from .. import VIEW_COURSE_RECURSIVE_BUCKET
from .. import VIEW_COURSE_ENROLLMENT_ROSTER

ASSETS_FOLDER = ASSETS_FOLDER
VIEW_CONTENTS = VIEW_CONTENTS
VIEW_COURSE_MAIL = VIEW_COURSE_MAIL
VIEW_CATALOG_ENTRY = VIEW_CATALOG_ENTRY
VIEW_COURSE_ACTIVITY = VIEW_COURSE_ACTIVITY
VIEW_COURSE_RECURSIVE = VIEW_COURSE_RECURSIVE
VIEW_COURSE_RECURSIVE_BUCKET = VIEW_COURSE_RECURSIVE_BUCKET
VIEW_COURSE_ENROLLMENT_ROSTER = VIEW_COURSE_ENROLLMENT_ROSTER

@interface.implementer(IPathAdapter)
class CourseAdminPathAdapter(Contained):

	__name__ = 'CourseAdmin'

	def __init__(self, context, request):
		self.context = context
		self.request = request
		self.__parent__ = context

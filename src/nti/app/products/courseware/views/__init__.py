#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
nti.app.products.courseware  $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.contained import Contained

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.courseware import MessageFactory

from nti.app.products.courseware import ASSETS_FOLDER
from nti.app.products.courseware import VIEW_CONTENTS
from nti.app.products.courseware import VIEW_COURSE_MAIL
from nti.app.products.courseware import VIEW_CATALOG_ENTRY
from nti.app.products.courseware import VIEW_COURSE_ACTIVITY
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE
from nti.app.products.courseware import SEND_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_DISCUSSIONS
from nti.app.products.courseware import ACCEPT_COURSE_INVITATION
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware import CHECK_COURSE_INVITATIONS_CSV
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE_BUCKET
from nti.app.products.courseware import VIEW_COURSE_ENROLLMENT_ROSTER

@interface.implementer(IPathAdapter)
class CourseAdminPathAdapter(Contained):

	__name__ = 'CourseAdmin'

	def __init__(self, context, request):
		self.context = context
		self.request = request
		self.__parent__ = context

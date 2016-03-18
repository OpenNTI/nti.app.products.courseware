#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseSourceFiler

from nti.app.products.courseware.resources.utils import get_assets_folder

from nti.contenttypes.courses.interfaces import ICourseInstance

@interface.implementer(ICourseSourceFiler)
class CourseSourceFiler(object):

	def __init__(self, context=None, user=None):
		self.user = user
		self.course = ICourseInstance(context)

	@property
	def root(self):
		result = ICourseRootFolder(self.course)
		return result

	@property
	def assets(self):
		result = get_assets_folder(self.course)
		return result

	def save(self, source, key, contentType=None, overwrite=False, **kwargs):
		_ = kwargs.get('bucket')

	def get(self, key):
		pass

	def remove(self, key):
		pass

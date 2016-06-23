#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os

from zope import interface

from nti.app.products.courseware.resources.utils import get_course_filer

from nti.app.products.courseware.utils.importer import transfer_resources_from_filer

from nti.cabinet.filer import transfer_to_native_file

from nti.contentlibrary.interfaces import IFilesystemBucket

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.parser import load_discussion
from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.importer import BaseSectionImporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionImporter

from nti.contenttypes.courses.utils import get_course_subinstances

@interface.implementer(ICourseSectionImporter)
class CourseDiscussionsImporter(BaseSectionImporter):

	def _process_resources(self, discussion, source_filer, target_filer):
		transfer_resources_from_filer(ICourseDiscussion,  # provided interface
									  discussion,
									  source_filer,
									  target_filer)

	def process(self, context, source_filer, writeout=True):
		course = ICourseInstance(context)
		# make sure Discussions are initialized
		getattr(course, 'Discussions')
		# write discussions directory structure
		root = course.root 
		bucket = path_to_discussions(course)
		if IFilesystemBucket.providedBy(root) and writeout:
			path = os.path.join(root.absolute_path, bucket)
			if not os.path.exists(path):
				os.makedirs(path)
		if source_filer.is_bucket(bucket):
			target_filer = get_course_filer(course)
			discussions = ICourseDiscussions(course)
			discussions.clear()  # clear first
			for key in source_filer.list(bucket):
				if source_filer.is_bucket(key):
					continue
				source = source_filer.get(key)
				if source is None:
					continue
				name = source.name
				__traceback_info__ = key, bucket
				discussion = load_discussion(name,
											 source,
											 discussions,
											 path=bucket)
				self._process_resources(discussion, source_filer, target_filer)
				if IFilesystemBucket.providedBy(root) and writeout:
					path = os.path.join(root.absolute_path, bucket)
					path = os.path.join(path, name)
					source = source_filer.get(key)  # get source again
					transfer_to_native_file(source, path)
		# process subinstances
		for subinstance in get_course_subinstances(course):
			self.process(subinstance, source_filer)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion
from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.discussions.parser import path_to_discussions

from nti.contenttypes.courses.exporter import BaseSectionExporter

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import StandardExternalFields

OID = StandardExternalFields.OID
NTIID = StandardExternalFields.NTIID

@interface.implementer(ICourseSectionExporter)
class CourseDiscussionsExporter(BaseSectionExporter):

	def _process_resources(self, discussion, ext_obj, target_filer):
		save_resources_to_filer(ICourseDiscussion, # provided interface
							    discussion,
							    target_filer, 
							    ext_obj)

	def _ext_obj(self, discussion):
		ext_obj = to_external_object(discussion, decorate=False)
		ext_obj.pop(NTIID, None)
		ext_obj.pop(OID, None)
		return ext_obj

	def export(self, context, filer, backup=True):
		course = ICourseInstance(context)
		bucket = path_to_discussions(course)
		discussions = ICourseDiscussions(course)
		for name, discussion in list(discussions.items()): # snapshop
			ext_obj = to_external_object(discussion, decorate=False)
			self._process_resources(discussion, ext_obj, filer)
			source = self.dump(ext_obj)
			filer.save(name, source, contentType="application/json",
				   	   bucket=bucket, overwrite=True)
		# process subinstances
		for sub_instance in get_course_subinstances(course):
			self.export(sub_instance, filer, backup)

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id: exporter.py 85599 2016-03-30 20:38:59Z carlos.sanchez $
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from StringIO import StringIO

import simplejson

from zope import interface

from nti.app.products.courseware.utils.exporter import save_resources_to_filer

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.interfaces import SECTIONS
from nti.contenttypes.courses.interfaces import DISCUSSIONS

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseSectionExporter

from nti.contenttypes.courses.utils import get_course_subinstances

from nti.externalization.externalization import to_external_object

@interface.implementer(ICourseSectionExporter)
class CourseDiscussionsExporter(object):

	def _process_resources(self, discussion, ext_obj, filer):
		save_resources_to_filer(ICourseDiscussions, discussion, filer, ext_obj)

	def export(self, context, filer):
		course = ICourseInstance(context)
		if ICourseSubInstance.providedBy(course):
			bucket = "%s/%s/%s" % (SECTIONS, course.__name__, DISCUSSIONS)
		else:
			bucket = DISCUSSIONS

		discussions = ICourseDiscussions(course)
		for name, discussion in list(discussions.items()):
			# export to json
			source = StringIO()
			ext_obj = to_external_object(discussion, decorate=False)
			self._process_resources(discussion, ext_obj, filer)
			simplejson.dump(ext_obj, source, indent=4)
			source.seek(0)
			# save in filer
			filer.save(name, source, contentType="text/json",
				   	   bucket=bucket, overwrite=True)
		# save outlines for subinstances
		for sub_instance in get_course_subinstances(course):
			if sub_instance.Outline is not course.Outline:
				self.export(sub_instance, filer)

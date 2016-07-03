#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import tempfile

from zope import component

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.views._utils import _parse_course

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ICourseExporter
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseExportFiler
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

def export_course(context):
	course = ICourseInstance(context)
	filer = ICourseExportFiler(course)
	try:
		# prepare filer
		filer.prepare()

		# export course
		exporter = component.getUtility(ICourseExporter)
		exporter.export(course, filer)

		# zip contents
		zip_file = filer.asZip(path=tempfile.mkdtemp())
		return zip_file
	finally:
		filer.reset()

def _export_course_response(context, response):
	zip_file = None
	try:
		zip_file = export_course(context)
		filename = os.path.split(zip_file)[1]
		response.content_encoding = str('identity')
		response.content_type = str('application/zip; charset=UTF-8')
		response.content_disposition = str('attachment; filename="%s"' % filename)
		response.body_file = open(zip_file, "rb")
		return response
	finally:
		if zip_file:
			os.remove(zip_file)

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name='Export',
			   permission=nauth.ACT_NTI_ADMIN)
class CourseExportView(AbstractAuthenticatedView):

	def __call__(self):
		return _export_course_response(self.context, self.request.response)
	
@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 name='ExportCourse',
			 context=CourseAdminPathAdapter,
			 permission=nauth.ACT_NTI_ADMIN)
class AdminExportCourseView(AbstractAuthenticatedView,
				 			ModeledContentUploadRequestUtilsMixin):

	def readInput(self, value=None):
		if self.request.body:
			result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		else:
			result = self.request.params
		return CaseInsensitiveDict(result)

	def __call__(self):
		values = self.readInput()
		context = _parse_course(values)
		return _export_course_response(context, self.request.response)

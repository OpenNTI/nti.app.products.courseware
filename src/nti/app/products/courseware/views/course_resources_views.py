#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.contentfolder.views import MkdirView
from nti.app.contentfolder.views import ImportView
from nti.app.contentfolder.views import MkdirsView
from nti.app.contentfolder.views import UploadView

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.app.products.courseware.views import VIEW_RESOURCES

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields

MIMETYPE = StandardExternalFields.MIMETYPE

@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=VIEW_RESOURCES,
			   permission=nauth.ACT_READ)
class CatalogEntryCourseFolderView(AbstractAuthenticatedView):

	def __call__(self):
		result = ICourseRootFolder(self.context)
		return result
	
@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='mkdir',
			   permission=nauth.ACT_UPDATE)
class CourseFolderMkdirView(MkdirView):

	default_folder_mime_type = CourseContentFolder.mimeType

	def readInput(self, value=None):
		data = MkdirView.readInput(self, value=value)
		data[MIMETYPE] = self.default_folder_mime_type
		return data

@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='mkdirs',
			   permission=nauth.ACT_UPDATE)
class CourseFolderMkdirsView(MkdirsView):
	folder_factory = CourseContentFolder

@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='upload',
			   permission=nauth.ACT_UPDATE)
class CourseFolderUploadView(UploadView):

	def factory(self, source):
		return CourseContentFile

@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='import',
			   permission=nauth.ACT_UPDATE)
class CourseFolderImportView(ImportView):

	folder_factory = CourseContentFolder

	def factory(self, filename):
		return CourseContentFile

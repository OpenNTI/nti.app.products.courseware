#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.contentfolder.views import MkdirView
from nti.app.contentfolder.views import DeleteView
from nti.app.contentfolder.views import MkdirsView
from nti.app.contentfolder.views import UploadView
from nti.app.contentfolder.views import UploadZipView

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.model import CourseContentFile
from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import StandardExternalFields

MIMETYPE = StandardExternalFields.MIMETYPE

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
			   name='upload_zip',
			   permission=nauth.ACT_UPDATE)
class CourseFolderUploadZipView(UploadZipView):

	folder_factory = CourseContentFolder

	def factory(self, filename):
		return CourseContentFile

def has_associations(obj):
	try:
		return obj.has_associations()
	except AttributeError:
		pass
	return False

@view_config(context=ICourseContentFile)
@view_config(context=ICourseContentImage)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='DELETE',
			   permission=nauth.ACT_DELETE)
class CourseResourceDeleteView(DeleteView):
	
	def _do_delete(self, theObject):
		try:
			if has_associations(theObject):
				raise_json_error(
						self.request,
						hexc.HTTPUnprocessableEntity,
						{
							u'message': _('File is referenced by other assets.'),
							u'code': 'CourseContentFileReferenceError',
						},
						None)
		except AttributeError:
			pass
		return DeleteView._do_delete(self, theObject)

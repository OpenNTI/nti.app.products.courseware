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

from nti.app.contentfolder.views import MkdirView
from nti.app.contentfolder.views import MkdirsView

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.app.products.courseware.resources.model import CourseContentFolder

from nti.dataserver import authorization as nauth

@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='mkdir',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseFolderMkdir(MkdirView):
	default_folder_mime_type = CourseContentFolder.mimeType

@view_config(context=ICourseRootFolder)
@view_config(context=ICourseContentFolder)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name='mkdirs',
			   permission=nauth.ACT_CONTENT_EDIT)
class CourseFolderMkdirs(MkdirsView):	
	folder_factory = CourseContentFolder

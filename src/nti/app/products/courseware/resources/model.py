#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from zope.container.contained import Contained

from nti.app.products.courseware.resources.interfaces import ICourseRootFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentResource

from nti.common.property import CachedProperty

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.interfaces import IRootFolder

from nti.contentfolder.model import RootFolder
from nti.contentfolder.model import ContentFolder

@interface.implementer(ICourseRootFolder)
class CourseRootFolder(RootFolder):
	pass

@interface.implementer(ICourseContentFolder)
class CourseContentFolder(ContentFolder):
	mimeType = mime_type = str('application/vnd.nextthought.courseware.contentfolder')

@interface.implementer(ICourseContentResource)
class CourseContentResource(Contained):
	
	@CachedProperty('__parent__')
	def path(self):
		context = self
		result = []
		while context is not None and not IRootFolder.providedBy(context):
			try:
				result.append(context.__name__)
				context = context.__parent__
			except AttributeError:
				break
		result.reverse()
		return '/'.join(result)

@interface.implementer(ICourseContentFile)
class CourseContentFile(ContentBlobFile, CourseContentResource):
	pass

@interface.implementer(ICourseContentImage)
class CourseContentImage(ContentBlobImage, CourseContentResource):
	pass

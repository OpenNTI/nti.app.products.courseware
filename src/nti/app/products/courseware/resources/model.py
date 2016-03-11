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
from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.model import RootFolder
from nti.contentfolder.model import ContentFolder

@interface.implementer(ICourseRootFolder)
class CourseRootFolder(RootFolder):
	pass

@interface.implementer(ICourseContentFolder)
class CourseContentFolder(ContentFolder):
	mimeType = mime_type = str('application/vnd.nextthought.courseware.contentfolder')

@interface.implementer(ICourseContentFile)
class CourseContentFile(ContentBlobFile):
	pass

@interface.implementer(ICourseContentImage)
class CourseContentImage(ContentBlobImage):
	pass

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

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentfolder.model import RootFolder
from nti.contentfolder.model import ContentFolder

from nti.contentfolder.utils import compute_path

from nti.property.property import CachedProperty


class AssociationsMixin(object):

    def __init__(self, *args, **kwargs):
        super(CourseContentResource, self).__init__(*args, **kwargs)

    def has_associations(self):
        result = False
        for value in list(self.values()):  # snapshot
            try:
                result = value.has_associations() or result
                if result:
                    break
            except AttributeError:
                pass
        return result


@interface.implementer(ICourseRootFolder)
class CourseRootFolder(RootFolder, AssociationsMixin):
    pass


@interface.implementer(ICourseContentResource)
class CourseContentResource(Contained):

    def __init__(self, *args, **kwargs):
        super(CourseContentResource, self).__init__(*args, **kwargs)

    @CachedProperty('__parent__', '__name__')
    def path(self):
        return compute_path(self)


@interface.implementer(ICourseContentFolder)
class CourseContentFolder(CourseContentResource, ContentFolder, AssociationsMixin):
    mimeType = mime_type = u'application/vnd.nextthought.courseware.contentfolder'


@interface.implementer(ICourseContentFile)
class CourseContentFile(CourseContentResource, ContentBlobFile):
    pass


@interface.implementer(ICourseContentImage)
class CourseContentImage(CourseContentResource, ContentBlobImage):
    pass

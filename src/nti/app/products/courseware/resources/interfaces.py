#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class

from zope import interface

from nti.cabinet.interfaces import ISourceFiler

from nti.contentfile.interfaces import IContentBlobFile
from nti.contentfile.interfaces import IContentBlobImage

from nti.contentfolder.interfaces import IRootFolder
from nti.contentfolder.interfaces import ILockedFolder
from nti.contentfolder.interfaces import IContentFolder

from nti.schema.field import ValidTextLine

logger = __import__('logging').getLogger(__name__)


class IAssociationsMixin(interface.Interface):

    def has_associations():
        """
        return if this object's children has any associations
        """


class ICourseRootFolder(IRootFolder, IAssociationsMixin):
    pass


class ICourseContentResource(interface.Interface):

    path = ValidTextLine(title=u"the abs path to this resource",
                         required=False, readonly=True)


class ICourseContentFolder(IContentFolder,
                           ICourseContentResource,
                           IAssociationsMixin):
    pass


class ICourseLockedFolder(ICourseContentFolder, ILockedFolder):
    pass


class ICourseContentFile(IContentBlobFile, ICourseContentResource):
    pass


class ICourseContentImage(IContentBlobImage, ICourseContentResource):
    pass


class ICourseSourceFiler(ISourceFiler):
    pass

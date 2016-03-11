#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.contentfile.interfaces import IContentBlobFile
from nti.contentfile.interfaces import IContentBlobImage

from nti.contentfolder.interfaces import IRootFolder
from nti.contentfolder.interfaces import IContentFolder

class ICourseRootFolder(IRootFolder):
    pass

class ICourseContentFolder(IContentFolder):
    pass

class ICourseContentFile(IContentBlobFile):
    pass

class ICourseContentImage(IContentBlobImage):
    pass
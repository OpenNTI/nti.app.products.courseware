#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope.deprecation import deprecated

deprecated('ValidatingSite', 'No longer used')
class ValidatingSite(object):
    pass


deprecated('ValidatingMimeType', 'No longer used')
class ValidatingMimeType(object):
    pass


deprecated('ValidatingCourse', 'No longer used')
class ValidatingCourse(object):
    pass


deprecated('ValidatingCreator', 'No longer used')
class ValidatingCreator(object):
    pass


deprecated('ValidatingContentType', 'No longer used')
class ValidatingContentType(object):
    pass


deprecated('ValidatingAssociations', 'No longer used')
class ValidatingAssociations(object):
    pass

import zope.deferredimport
zope.deferredimport.initialize()
zope.deferredimport.deprecated(
    "Import from nti.contentfolder.index instead",
    NameIndex='nti.contentfolder.index:NameIndex',
    PathIndex='nti.contentfolder.index:PathIndex',
    SiteIndex='nti.contentfolder.index:SiteIndex',
    CreatorIndex='nti.contentfolder.index:CreatorIndex',
    FilenameIndex='nti.contentfolder.index:FilenameIndex',
    MimeTypeIndex='nti.contentfolder.index:MimeTypeIndex',
    CourseIndex='nti.contentfolder.index:ContainerIdIndex',
    CreatedTimeIndex='nti.contentfolder.index:CreatedTimeIndex',
    ContentTypeIndex='nti.contentfolder.index:ContentTypeIndex',
    AssociationsIndex='nti.contentfolder.index:AssociationsIndex',
    LastModifiedIndex='nti.contentfolder.index:LastModifiedIndex',
    CourseResourcesCatalog='nti.contentfolder.index:ContentResourcesCatalog')

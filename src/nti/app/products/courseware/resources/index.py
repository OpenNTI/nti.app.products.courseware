#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.app.products.courseware.resources.interfaces import ICourseContentFile
from nti.app.products.courseware.resources.interfaces import ICourseContentImage
from nti.app.products.courseware.resources.interfaces import ICourseContentFolder
from nti.app.products.courseware.resources.interfaces import ICourseContentResource

from nti.base._compat import unicode_

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.site.interfaces import IHostPolicyFolder

from nti.traversal.traversal import find_interface

from nti.zope_catalog.catalog import Catalog

from nti.zope_catalog.datetime import TimestampToNormalized64BitIntNormalizer

from nti.zope_catalog.index import AttributeSetIndex
from nti.zope_catalog.index import AttributeValueIndex
from nti.zope_catalog.index import NormalizationWrapper
from nti.zope_catalog.index import IntegerValueIndex as RawIntegerValueIndex

from nti.zope_catalog.interfaces import IMetadataCatalog

CATALOG_NAME = 'nti.dataserver.++etc++course-resources'

#: Filename index
IX_FILENAME = 'filename'

#: Name index
IX_NAME = 'name'

#: Path index
IX_PATH = 'path'

#: Coursee index
IX_ENTRY = IX_COURSE = 'course'

#: Site index
IX_SITE = 'site'

#: MimeType index
IX_MIMETYPE = 'mimeType'

#: Creator index
IX_CREATOR = 'creator'

#: Content index
IX_CONTENTTYPE = 'contentType'

#: Created time
IX_CREATEDTIME = 'createdTime'

#: Last time index
IX_LASTMODIFIED = 'lastModified'

#: Associations index
IX_ASSOCIATIONS = 'associations'


class ValidatingMimeType(object):

    __slots__ = (b'mimeType',)

    def __init__(self, obj, default=None):
        if ICourseContentFile.providedBy(obj):
            self.mimeType = u'application/vnd.nextthought.courseware.contentfile'
        elif ICourseContentImage.providedBy(obj):
            self.mimeType = u'application/vnd.nextthought.courseware.contentimage'
        elif ICourseContentFolder.providedBy(obj):
            self.mimeType = getattr(obj, 'mimeType', None)

    def __reduce__(self):
        raise TypeError()


class MimeTypeIndex(AttributeValueIndex):
    default_field_name = 'mimeType'
    default_interface = ValidatingMimeType


class ValidatingSite(object):

    __slots__ = (b'site',)

    def __init__(self, obj, default=None):
        if ICourseContentResource.providedBy(obj):
            folder = find_interface(obj, IHostPolicyFolder, strict=False)
            if folder is not None:
                self.site = unicode_(folder.__name__)

    def __reduce__(self):
        raise TypeError()


class SiteIndex(AttributeValueIndex):
    default_field_name = 'site'
    default_interface = ValidatingSite


class ValidatingCourse(object):
    """
    The "interface" we adapt to to find the grade value course.
    """

    __slots__ = (b'ntiid',)

    def __init__(self, obj, default=None):
        if ICourseContentResource.providedBy(obj):
            course = find_interface(obj, ICourseInstance, strict=False)
            entry = ICourseCatalogEntry(course, None)
            if entry is not None:
                self.ntiid = unicode_(entry.ntiid)

    def __reduce__(self):
        raise TypeError()


class CourseIndex(AttributeValueIndex):
    default_field_name = 'ntiid'
    default_interface = ValidatingCourse


class ValidatingCreator(object):

    __slots__ = (b'creator',)

    def __init__(self, obj, default=None):
        if ICourseContentResource.providedBy(obj):
            creator = getattr(obj, 'creator', None)
            creator = getattr(creator, 'username', creator)
            creator = getattr(creator, 'id', creator)
            if creator:
                self.creator = unicode_(creator.lower())

    def __reduce__(self):
        raise TypeError()


class CreatorIndex(AttributeValueIndex):
    default_field_name = 'creator'
    default_interface = ValidatingCreator


class PathIndex(AttributeValueIndex):
    default_field_name = 'path'
    default_interface = ICourseContentResource


class ValidatingContentType(object):

    __slots__ = (b'contentType',)

    def __init__(self, obj, default=None):
        if     ICourseContentFile.providedBy(obj) \
            or ICourseContentImage.providedBy(obj):
            self.contentType = obj.contentType

    def __reduce__(self):
        raise TypeError()


class ContentTypeIndex(AttributeValueIndex):
    default_field_name = 'contentType'
    default_interface = ValidatingContentType


class FilenameIndex(AttributeValueIndex):
    default_field_name = 'filename'
    default_interface = ICourseContentResource


class NameIndex(AttributeValueIndex):
    default_field_name = 'name'
    default_interface = ICourseContentResource


class CreatedTimeRawIndex(RawIntegerValueIndex):
    pass


def CreatedTimeIndex(family=None):
    return NormalizationWrapper(field_name='createdTime',
                                interface=ICourseContentResource,
                                index=CreatedTimeRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class LastModififedRawIndex(RawIntegerValueIndex):
    pass


def LastModifiedIndex(family=None):
    return NormalizationWrapper(field_name='lastModified',
                                interface=ICourseContentResource,
                                index=CreatedTimeRawIndex(family=family),
                                normalizer=TimestampToNormalized64BitIntNormalizer())


class ValidatingAssociations(object):

    __slots__ = (b'associations',)

    def __init__(self, obj, default=None):
        if     ICourseContentFile.providedBy(obj) \
            or ICourseContentImage.providedBy(obj):
            intid = component.queryUtility(IIntIds)
            if intid is not None and obj.has_associations():
                ids = {intid.queryId(x) for x in obj.associations()}
                ids.discard(None)
                self.associations = tuple(ids)

    def __reduce__(self):
        raise TypeError()


class AssociationsIndex(AttributeSetIndex):
    default_field_name = 'associations'
    default_interface = ValidatingAssociations


@interface.implementer(IMetadataCatalog)
class CourseResourcesCatalog(Catalog):

    super_index_doc = Catalog.index_doc

    def index_doc(self, docid, ob):
        pass

    def force_index_doc(self, docid, ob):
        self.super_index_doc(docid, ob)


def create_course_resources_catalog(catalog=None, family=None):
    if catalog is None:
        catalog = CourseResourcesCatalog(family=family)
    for name, clazz in ((IX_NAME, NameIndex),
                        (IX_PATH, PathIndex),
                        (IX_SITE, SiteIndex),
                        (IX_COURSE, CourseIndex),
                        (IX_CREATOR, CreatorIndex),
                        (IX_FILENAME, FilenameIndex),
                        (IX_MIMETYPE, MimeTypeIndex),
                        (IX_CONTENTTYPE, ContentTypeIndex),
                        (IX_CREATEDTIME, CreatedTimeIndex),
                        (IX_LASTMODIFIED, LastModifiedIndex),
                        (IX_ASSOCIATIONS, AssociationsIndex)):
        index = clazz(family=family)
        locate(index, catalog, name)
        catalog[name] = index
    return catalog


def get_catalog(registry=component):
    catalog = registry.queryUtility(IMetadataCatalog, name=CATALOG_NAME)
    return catalog


def install_course_resources_catalog(site_manager_container, intids=None):
    lsm = site_manager_container.getSiteManager()
    intids = lsm.getUtility(IIntIds) if intids is None else intids
    catalog = get_catalog(registry=lsm)
    if catalog is not None:
        return catalog

    catalog = CourseResourcesCatalog(family=intids.family)
    locate(catalog, site_manager_container, CATALOG_NAME)
    intids.register(catalog)
    lsm.registerUtility(catalog, provided=IMetadataCatalog, name=CATALOG_NAME)

    catalog = create_course_resources_catalog(catalog=catalog, family=intids.family)
    for index in catalog.values():
        intids.register(index)
    return catalog

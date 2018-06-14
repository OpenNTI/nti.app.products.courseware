#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import uuid

from datetime import datetime

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from nti.app.products.courseware.interfaces import IEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptions
from nti.app.products.courseware.interfaces import IOpenEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider
from nti.app.products.courseware.interfaces import IExternalEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptionContainer
from nti.app.products.courseware.interfaces import IAvailableEnrollmentOptionProvider

from nti.containers.containers import CaseInsensitiveCheckingLastModifiedBTreeContainer

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.coremetadata.interfaces import SYSTEM_USER_NAME

from nti.dublincore.time_mixins import PersistentCreatedAndModifiedTimeObject

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.externalization.persistence import NoPickle

from nti.externalization.representation import WithRepr

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import make_specific_safe

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

logger = __import__('logging').getLogger(__name__)


@WithRepr
@NoPickle
@EqHash('Name')
@interface.implementer(IEnrollmentOption)
class EnrollmentOption(SchemaConfigured):

    __parent__ = None
    __external_can_create__ = False
    __external_class_name__ = "EnrollmentOption"
    mime_type = mimeType = 'application/vnd.nextthought.courseware.enrollmentoption'

    CatalogEntryNTIID = FP(IEnrollmentOption['CatalogEntryNTIID'])

    @property
    def Name(self):
        return self.__external_class_name__
    __name__ = Name

    @Name.setter
    def Name(self, value):
        pass


@EqHash('Name', 'Enabled')
@interface.implementer(IOpenEnrollmentOption)
class OpenEnrollmentOption(EnrollmentOption):

    __external_class_name__ = "OpenEnrollment"
    mime_type = mimeType = 'application/vnd.nextthought.courseware.openenrollmentoption'

    Enabled = FP(IOpenEnrollmentOption['Enabled'])

    IsEnabled = alias('Enabled')


def _generate_ntiid(nttype, provider=u'NTI', now=None):
    now = datetime.utcnow() if now is None else now
    dstr = now.strftime("%Y%m%d%H%M%S %f")
    rand = str(uuid.uuid4().time_low)
    specific = make_specific_safe(u"%s_%s_%s" % (SYSTEM_USER_NAME, dstr, rand))
    result = make_ntiid(provider=provider,
                        nttype=nttype,
                        specific=specific)
    return result


def generate_external_enrollment_ntiid(provider=u'NTI', now=None):
    return _generate_ntiid('ExternalEnrollmentOption', provider, now)


@interface.implementer(IExternalEnrollmentOption)
class ExternalEnrollmentOption(EnrollmentOption,
                               Contained,
                               PersistentCreatedAndModifiedTimeObject):

    createDirectFieldProperties(IExternalEnrollmentOption)

    __external_can_create__ = True
    __external_class_name__ = __name__ = u"ExternalEnrollment"
    mime_type = mimeType = 'application/vnd.nextthought.courseware.externalenrollmentoption'

    def __init__(self, *args, **kwargs):
        super(ExternalEnrollmentOption, self).__init__(*args, **kwargs)
        SchemaConfigured.__init__(self, *args, **kwargs)

    @Lazy
    def ntiid(self):
        return generate_external_enrollment_ntiid()


def get_available_enrollment_options(course):
    """
    Return the :class:`IEnrollmentOption` objects available to be
    placed on a course.
    """
    result = list()
    for provider in component.subscribers((course,), IAvailableEnrollmentOptionProvider):
        for option in provider.iter_options():
            result.append(option)
    return result


@WithRepr
@NoPickle
@interface.implementer(IEnrollmentOptions, IInternalObjectExternalizer)
class EnrollmentOptions(LocatedExternalDict):

    __external_can_create__ = False
    __external_class_name__ = "EnrollmentOptions"
    mime_type = mimeType = 'application/vnd.nextthought.courseware.enrollmentoptions'

    def append(self, option):
        self[option.Name] = option

    def __setitem__(self, key, value):
        assert IEnrollmentOption.providedBy(value)
        assert value.Name, 'Missing Enrollment option name'
        value.__parent__ = self
        return LocatedExternalDict.__setitem__(self, key, value)

    def toExternalObject(self, *args, **kwargs):
        result = LocatedExternalDict()
        result[CLASS] = self.__external_class_name__
        result[MIMETYPE] = self.mimeType
        items = result[ITEMS] = {}
        for value in list(self.values()):
            items[value.Name] = to_external_object(value, *args, **kwargs)
        return result


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IEnrollmentOptionProvider)
class OpenEnrollmentOptionProvider(object):

    def __init__(self, context):
        self.context = context

    def iter_options(self):
        result = OpenEnrollmentOption()
        result.CatalogEntryNTIID = self.context.ntiid
        result.Enabled = not INonPublicCourseInstance.providedBy(self.context) \
                     and not IDenyOpenEnrollment.providedBy(self.context)
        return (result,)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IEnrollmentOptionProvider)
class ContainerEnrollmentOptionProvider(object):

    def __init__(self, context):
        self.context = context

    def iter_options(self):
        container = IEnrollmentOptionContainer(self.context)
        return tuple(container.values())


@interface.implementer(IEnrollmentOptionContainer)
class EnrollmentOptionContainer(CaseInsensitiveCheckingLastModifiedBTreeContainer,
                                SchemaConfigured):
    createDirectFieldProperties(IEnrollmentOptionContainer)

    __parent__ = None
    __name__ = 'EnrollmentOptions'
    __external_class_name__ = 'EnrollmentOptionContainer'
    mimeType = 'application/vnd.nextthought.courseware.enrollmentoptioncontainer'


@component.adapter(IEnrollmentOptionContainer)
@interface.implementer(IEnrollmentOptionContainer, IInternalObjectExternalizer)
class EnrollmentOptionContainerExternalizer(object):

    def __init__(self, container):
        self.container = container

    def toExternalObject(self, *args, **kwargs):
        result = LocatedExternalDict()
        result[CLASS] = self.container.__external_class_name__
        result[MIMETYPE] = self.container.mimeType
        items = result[ITEMS] = []
        for value in list(self.container.values()):
            items.append(value)
        result[ITEM_COUNT] = len(items)
        course = find_interface(self.container, ICourseInstance)
        result['AvailableEnrollmentOptions'] = get_available_enrollment_options(course)
        return result


@interface.implementer(IAvailableEnrollmentOptionProvider)
class _AvailableEnrollmentOptionProvider(object):

    def __init__(self, course):
        self.course = course

    def iter_options(self):
        result = list()
        result.append(ExternalEnrollmentOption(enrollment_url='https://'))
        return result

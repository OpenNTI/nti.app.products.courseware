#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.schema.fieldproperty import FieldPropertyStoredThroughField as FP

from nti.app.products.courseware.interfaces import IEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptions
from nti.app.products.courseware.interfaces import IOpenEnrollmentOption
from nti.app.products.courseware.interfaces import IEnrollmentOptionProvider

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.externalization.persistence import NoPickle

from nti.externalization.representation import WithRepr

from nti.property.property import alias

from nti.schema.eqhash import EqHash

from nti.schema.field import SchemaConfigured

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
MIMETYPE = StandardExternalFields.MIMETYPE


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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.externalization.persistence import NoPickle
from nti.externalization.representation import WithRepr
from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object
from nti.externalization.interfaces import IInternalObjectExternalizer

from nti.schema.schema import EqHash

from .interfaces import IEnrollmentOption
from .interfaces import IEnrollmentOptions
from .interfaces import IOpenEnrollmentOption

CLASS = StandardExternalFields.CLASS
MIMETYPE = StandardExternalFields.MIMETYPE

@interface.implementer(IOpenEnrollmentOption)
@WithRepr
@NoPickle
@EqHash('Name')
class OpenEnrollmentOption(object):

	__parent__ = None
	__external_can_create__ = False
	__external_class_name__ = "OpenEnrollment"
	mime_type = mimeType = 'application/vnd.nextthought.courseware.openenrollmentoption'

	@property
	def Name(self):
		return 'OpenEnrollment'
	__name__ = Name
		
@interface.implementer(IEnrollmentOptions, IInternalObjectExternalizer)
@WithRepr
@NoPickle
class EnrollmentOptions(LocatedExternalDict):
	
	__external_can_create__ = False
	__external_class_name__ = "EnrollmentOptions"
	mime_type = mimeType = 'application/vnd.nextthought.courseware.enrollmentoptions'

	def append(self, option):
		self[option.Name] = option

	def __setitem__(self, key, value):
		assert IEnrollmentOption.providedBy(value)
		assert value.Name
		value.__parent__ = self
		return LocatedExternalDict.__setitem__(self, key, value)

	def toExternalObject(self, *args, **kwargs):
		result = LocatedExternalDict()
		result[CLASS] = self.__external_class_name__
		result[MIMETYPE] = self.mimeType
		for value in self.values():
			result[value.Name] = to_external_object(value)
		return result

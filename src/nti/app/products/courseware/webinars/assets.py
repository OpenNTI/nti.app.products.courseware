#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.cachedescriptors.property import readproperty

from zope.intid.interfaces import IntIdMissingError

from nti.app.products.courseware.webinars import WEBINAR_ASSET_MIME_TYPE

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.contenttypes.presentation.mixins import PersistentPresentationAsset

from nti.property.property import alias

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.wref.interfaces import IWeakRef

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IWebinarAsset)
class WebinarAsset(PersistentPresentationAsset):

    createDirectFieldProperties(IWebinarAsset)
    mimeType = mime_type = WEBINAR_ASSET_MIME_TYPE
    __external_class_name__ = "WebinarAsset"

    Creator = alias('creator')
    desc = alias('description')
    __name__ = alias('ntiid')

    _webinar = None

    nttype = u'NTIWebinarAsset'

    @readproperty
    def ntiid(self):  # pylint: disable=method-hidden
        self.ntiid = self.generate_ntiid(self.nttype)
        return self.ntiid

    @property
    def webinar(self):
        try:
            result = self._webinar()
        except (TypeError, AttributeError):
            result = self._webinar
        return result

    @webinar.setter
    def webinar(self, value):
        try:
            self._webinar = IWeakRef(value, value)
        except IntIdMissingError:
            self._webinar = value

    @property
    def target(self):
        return getattr(self.webinar, 'ntiid', '')



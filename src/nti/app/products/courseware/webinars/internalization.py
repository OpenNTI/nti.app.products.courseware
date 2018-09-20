#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six

from zope import component
from zope import interface

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.app.products.webinar.interfaces import IWebinarClient
from nti.app.products.webinar.interfaces import IGoToWebinarAuthorizedIntegration

from nti.externalization.datastructures import InterfaceObjectIO

from nti.externalization.interfaces import IInternalObjectUpdater

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IInternalObjectUpdater)
class WebinarAssetUpdater(InterfaceObjectIO):

    _ext_iface_upper_bound = IWebinarAsset

    def updateFromExternalObject(self, parsed, *args, **kwargs):
        webinar_data = parsed.get('webinar')
        if isinstance(webinar_data, six.string_types):
            # The client may give us a webinar key here instead of the
            # actual webinar object; if so, we must resolve it.
            webinar_integration = component.getUtility(IGoToWebinarAuthorizedIntegration)
            client = IWebinarClient(webinar_integration)
            webinar = client.get_webinar(webinar_data)
            if webinar is None:
                # We'll fail validation if none
                logger.warning('Could not resolve webinar with key (%s)',
                               webinar_data)
            parsed['webinar'] = webinar
        return super(WebinarAssetUpdater, self).updateFromExternalObject(parsed, *args, **kwargs)

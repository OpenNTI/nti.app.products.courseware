#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             renderer='rest',
             context=ICourseInstance,
             permission=nauth.ACT_READ,
             name='common_cartridge')
class CommonCartridgeExportView(AbstractAuthenticatedView):

    def __call__(self):
        cartridge = IIMSCommonCartridge(self.context)
        return cartridge

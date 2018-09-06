#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from zope.event import notify

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware import MessageFactory as _

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent

from nti.dataserver import authorization as nauth

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@view_config(context=ICourseContentPackageBundle)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_UPDATE)
class ContentPackageBundlePutView(UGDPutView):

    def __call__(self):
        # pylint: disable=no-member
        old_packages = set(self.context.ContentPackages or ())
        try:
            result = UGDPutView.__call__(self)
        except KeyError:
            raise_json_error(self.request,
                             hexc.HTTPConflict,
                             {
                                 'message': _(u"Content Package Not Found."),
                                 'code': 'ContentPackageNotFound',
                             },
                             None)
        new_packages = set(self.context.ContentPackages or ())
        removed = old_packages.difference(new_packages)
        added = new_packages.difference(old_packages)
        if added or removed:
            course = find_interface(result, ICourseInstance, strict=False)
            notify(CourseBundleWillUpdateEvent(course, added, removed))
        else:
            logger.warning('Updating bundle without changing contents')
        return result

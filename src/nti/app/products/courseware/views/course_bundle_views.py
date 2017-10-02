#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from requests.structures import CaseInsensitiveDict

import six

from zope.event import notify

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import update_object_from_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.appserver.ugd_edit_views import UGDPutView

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle

from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@view_config(context=ICourseContentPackageBundle)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='PUT',
               permission=nauth.ACT_UPDATE)
class ContentPackageBundlePutView(UGDPutView):

    def __call__(self):
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
            logger.warn('Updating bundle without changing contents')
        return result


class ContentPackageBundleMixinView(AbstractAuthenticatedView,
                                    ModeledContentUploadRequestUtilsMixin):
    
    def readInput(self, value=None):
        result = super(ContentPackageBundleMixinView, self).readInput(value)
        return CaseInsensitiveDict(result)

    def get_ntiids(self):
        data = self.readInput()
        ntiids =   data.get('ntiid') \
                or data.get('ntiids') \
                or data.get('pacakge') \
                or data.get('pacakges')
        if isinstance(ntiids, six.string_types):
            ntiids = ntiids.split()
        if not ntiids:
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"No content package specified."),
                             },
                             None)
        return set(ntiids)


@view_config(name='add')
@view_config(name='AddPackage')
@view_config(name='AddPackages')
@view_config(context=ICourseContentPackageBundle)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_UPDATE)
class ContentPackageBundleAddPackagesView(ContentPackageBundleMixinView):

    def __call__(self):
        ntiids = self.get_ntiids()
        packages = {x.ntiid for x in self.context.ContentPackages or ()}
        ntiids.update(packages)
        added = ntiids.difference(packages)
        if added:
            ext_obj = {'ContentPackages': sorted(ntiids)}
            update_object_from_external_object(self.context, ext_obj, True)
            added = [find_object_with_ntiid(x) for x in added]
            course = find_interface(self.context, ICourseInstance, strict=False)
            notify(CourseBundleWillUpdateEvent(course, added, ()))
        return self.context


@view_config(name='remove')
@view_config(name='RemovePackage')
@view_config(name='RemovePackages')
@view_config(context=ICourseContentPackageBundle)
@view_defaults(route_name='objects.generic.traversal',
               name="remove",
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_UPDATE)
class ContentPackageBundleRemovePackagesView(ContentPackageBundleMixinView):

    def __call__(self):
        ntiids = self.get_ntiids()
        packages = {x.ntiid for x in self.context.ContentPackages or ()}
        removed = packages.difference(ntiids)
        if removed:
            ext_obj = {'ContentPackages': sorted(removed)}
            update_object_from_external_object(self.context, ext_obj, True)
            removed = [find_object_with_ntiid(x) for x in removed]
            course = find_interface(self.context, ICourseInstance, strict=False)
            notify(CourseBundleWillUpdateEvent(course, (), removed))
        return self.context

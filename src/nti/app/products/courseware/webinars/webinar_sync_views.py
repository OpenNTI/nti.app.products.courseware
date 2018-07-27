#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from zope import component

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware import VIEW_UPDATE_WEBINAR_PROGRESS
from nti.app.products.courseware import VIEW_ALL_SITE_UPDATE_WEBINAR_PROGRESS

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.webinars.completion import update_webinar_completion

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset

from nti.app.products.webinar.progress import should_update_progress
from nti.app.products.webinar.progress import update_webinar_progress

from nti.site.site import get_component_hierarchy_names

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict

from nti.site.hostpolicy import run_job_in_all_host_sites

from nti.site.site import getSite

logger = __import__('logging').getLogger(__name__)


def get_webinar_assets():
    catalog = get_library_catalog()
    intids = component.getUtility(IIntIds)
    sites = get_component_hierarchy_names()
    provided = (IWebinarAsset,)
    rs = catalog.search_objects(sites=sites,
                                intids=intids,
                                provided=provided)
    return tuple(rs)


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=CourseAdminPathAdapter,
             name=VIEW_UPDATE_WEBINAR_PROGRESS,
             permission=nauth.ACT_NTI_ADMIN)
class AllCourseWebinarProgressView(AbstractAuthenticatedView):
    """
    A view to update progress for all webinars in all courses, as necessary.
    """

    def process_asset(self, asset):
        webinar = asset.webinar
        updated = False
        if webinar is None:
            continue
        if should_update_progress(webinar):
            updated = True
            course = ICourseInstance(asset)
            logger.info('Updating webinar progress (%s)', webinar)
            update_webinar_progress(webinar)
            update_webinar_completion(asset, webinar, course)
        return updated

    def __call__(self):
        t0 = time.time()
        assets = get_webinar_assets()
        asset_count = 0
        webinar_updated_count = 0
        result = LocatedExternalDict()
        for asset in assets:
            asset_count += 1
            did_update = self.process_asset(asset)
            if did_update:
                webinar_updated_count += 1
        logger.info('Finished updating webinars in %.2fs (asset_count=%s) (updated_count=%s)',
                    time.time() - t0,
                    asset_count,
                    webinar_updated_count)
        result['asset_count'] = asset_count
        result['webinar_updated_count'] = webinar_updated_count
        return result


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=CourseAdminPathAdapter,
             name=VIEW_ALL_SITE_UPDATE_WEBINAR_PROGRESS,
             permission=nauth.ACT_NTI_ADMIN)
class AllSiteCourseWebinarProgressUpdateView(AbstractAuthenticatedView):
    """
    A view to update progress for all webinars in all sites and courses.
    """

    def __call__(self):
        seen = set()
        result = LocatedExternalDict()

        def update_site_progress():
            t0 = time.time()
            assets = get_webinar_assets()
            asset_count = 0
            webinar_updated_count = 0
            for asset in assets:
                if asset.ntiid in seen:
                    continue
                seen.add(asset.ntiid)
                asset_count += 1
                did_update = self.process_asset(asset)
                if did_update:
                    webinar_updated_count += 1
            site_name = getSite().__name__
            site_dict = dict()
            site_dict['asset_count'] = asset_count
            site_dict['webinar_updated_count'] = webinar_updated_count
            result[site_name] = site_dict
            logger.info('[%s] Finished updating webinars in %.2fs (asset_count=%s) (updated_count=%s)',
                        getSite().__name__,
                        time.time() - t0,
                        asset_count,
                        webinar_updated_count)

        run_job_in_all_host_sites(update_site_progress)
        return result

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

from nti.app.products.courseware import VIEW_UPDATE_WEBINARS
from nti.app.products.courseware import VIEW_UPDATE_WEBINAR_PROGRESS
from nti.app.products.courseware import VIEW_ALL_SITE_UPDATE_WEBINARS
from nti.app.products.courseware import VIEW_ALL_SITE_UPDATE_WEBINAR_PROGRESS

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.app.products.courseware.webinars.completion import update_webinar_completion

from nti.app.products.courseware.webinars.interfaces import IWebinarAsset
from nti.app.products.courseware.webinars.interfaces import ICourseWebinarContainer

from nti.app.products.webinar.interfaces import IWebinarClient

from nti.app.products.webinar.progress import should_update_progress
from nti.app.products.webinar.progress import update_webinar_progress

from nti.site.site import get_component_hierarchy_names

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict

from nti.externalization.internalization import update_from_external_object

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
            return updated
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
        logger.info('Finished updating webinar progress in %.2fs (asset_count=%s) (updated_count=%s)',
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
class AllSiteCourseWebinarProgressUpdateView(AllCourseWebinarProgressView):
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
            if webinar_updated_count:
                site_name = getSite().__name__
                site_dict = dict()
                site_dict['asset_count'] = asset_count
                site_dict['webinar_progress_updated_count'] = webinar_updated_count
                result[site_name] = site_dict
            logger.info('[%s] Finished updating webinar progress in %.2fs (asset_count=%s) (updated_count=%s)',
                        getSite().__name__,
                        time.time() - t0,
                        asset_count,
                        webinar_updated_count)

        run_job_in_all_host_sites(update_site_progress)
        return result


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=CourseAdminPathAdapter,
             name=VIEW_UPDATE_WEBINARS,
             permission=nauth.ACT_NTI_ADMIN)
class AllWebinarUpdateView(AbstractAuthenticatedView):
    """
    A view to update progress for all webinars in all courses, as necessary.
    """

    def process_webinar(self, webinar, webinar_ext_cache):
        result = False
        client = IWebinarClient(webinar, None)
        if client is None:
            logger.info("Cannot update webinar (%s) since we cannot obtain a client (unauthorized)",
                        webinar)
            return result

        try:
            key_to_webinar_dict = webinar_ext_cache[webinar.organizerKey]
        except KeyError:
            upcoming_webinars = client.get_upcoming_webinars(raw=True)
            if upcoming_webinars:
                key_to_webinar_dict = {unicode(x['webinarKey']):x for x in upcoming_webinars}
            else:
                key_to_webinar_dict = {}
            webinar_ext_cache[webinar.organizerKey] = key_to_webinar_dict

        webinar_ext = key_to_webinar_dict.get(webinar.webinarKey)

        if webinar_ext:
            update_from_external_object(webinar, webinar_ext)
            result = True
        else:
            # This is probably a webinar that has already past
            logger.debug('Webinar not found while updating (%s)', webinar)
        return result

    def process_course(self, course, webinar_ext_cache):
        webinar_container = ICourseWebinarContainer(course)
        update_count = 0
        # pylint: disable=too-many-function-args
        for webinar in webinar_container.values():
            did_update = self.process_webinar(webinar, webinar_ext_cache)
            if did_update:
                update_count += 1
        return update_count

    def process_site_courses(self, seen, intids):
        catalog = component.queryUtility(ICourseCatalog)
        result_count = 0
        course_count = 0
        webinar_ext_cache = {}
        if catalog is None or catalog.isEmpty():
            return result_count, course_count
        for entry in catalog.iterCatalogEntries():
            course = ICourseInstance(entry, None)
            doc_id = intids.queryId(course)
            if doc_id is None or doc_id in seen:
                continue
            seen.add(doc_id)
            update_count = self.process_course(course, webinar_ext_cache)
            if update_count:
                course_count += 1
            result_count += update_count
        return result_count, course_count

    def __call__(self):
        t0 = time.time()
        seen = set()
        intids = component.getUtility(IIntIds)
        update_count, course_count = self.process_site_courses(seen, intids)
        result = LocatedExternalDict()
        logger.info('Finished updating webinars in %.2fs (updated_count=%s) (course_count=%s)',
                    time.time() - t0,
                    update_count,
                    course_count)
        result['course_count'] = course_count
        result['webinar_updated_count'] = update_count
        return result


@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='POST',
             context=CourseAdminPathAdapter,
             name=VIEW_ALL_SITE_UPDATE_WEBINARS,
             permission=nauth.ACT_NTI_ADMIN)
class AllSiteWebinarUpdateView(AllWebinarUpdateView):
    """
    A view to update progress for all webinars in all sites and courses.
    """

    def __call__(self):
        seen = set()
        result = LocatedExternalDict()
        intids = component.getUtility(IIntIds)

        def update_site_webinars():
            t0 = time.time()
            update_count, course_count = self.process_site_courses(seen, intids)
            if update_count:
                site_name = getSite().__name__
                site_dict = dict()
                site_dict['course_count'] = course_count
                site_dict['webinar_updated_count'] = update_count
                result[site_name] = site_dict
            logger.info('[%s] Finished updating webinars in %.2fs (updated_count=%s) (course_count=%s)',
                        getSite().__name__,
                        time.time() - t0,
                        update_count,
                        course_count)

        run_job_in_all_host_sites(update_site_webinars)
        return result

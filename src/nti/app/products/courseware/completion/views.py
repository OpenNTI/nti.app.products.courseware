#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import shutil
import tempfile
import urllib
from mimetypes import guess_extension

import transaction
from datetime import datetime

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from slugify import slugify

from zc.displayname.interfaces import IDisplayNameGenerator

from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware import VIEW_CERTIFICATE
from nti.app.products.courseware import VIEW_CERTIFICATE_PREVIEW
from nti.app.products.courseware import VIEW_ACKNOWLEDGE_COMPLETION

from nti.app.products.courseware.completion.interfaces import ICourseCompletedNotification

from nti.app.products.courseware.completion.utils import ImageUtils

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.site.views.brand_views import SiteBrandUpdateBase

from nti.appserver.brand.interfaces import ISiteBrand

from nti.appserver.brand.utils import get_site_brand_name

from nti.appserver.interfaces import IDisplayableTimeProvider

from nti.appserver.policies.site_policies import guess_site_display_name

from nti.appserver.ugd_edit_views import UGDPutView

from nti.common.string import is_true

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICertificateRenderer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.catalog import CourseCatalogInstructorInfo

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.credit.interfaces import ICreditTranscript

from nti.dataserver import authorization as nauth

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.users.users import User

logger = __import__('logging').getLogger(__name__)


class EnrollmentProgressViewMixin(object):

    @Lazy
    def course(self):
        return self.context.CourseInstance

    @Lazy
    def user(self):
        username = self.context.Username
        return User.get_user(username)

    @Lazy
    def course_policy(self):
        return ICompletionContextCompletionPolicy(self.course, None)

    @Lazy
    def progress(self):
        return component.queryMultiAdapter((self.user, self.course), IProgress)


class CompletionViewMixin(object):

    Title = u'Completion Certificate'
    
    @Lazy
    def _certificate_renderer_name(self):
        """
        The named utility of the ICertificateRenderer to use.
        """
        raise NotImplementedError()

    @Lazy
    def _certificate_renderer(self):
        """
        The ICertificateRenderer
        """
        result = None
        if self._certificate_renderer_name:
            result = component.queryUtility(ICertificateRenderer, 
                                            name=self._certificate_renderer_name)
        if result is None:
            result = component.getUtility(ICertificateRenderer, name='default')
        return result

    @Lazy
    def _brand_name(self):
        display_name = get_site_brand_name()
        if display_name:
            display_name = display_name.strip()
        else:
            display_name = guess_site_display_name(self.request)
        return display_name

    @Lazy
    def _brand(self):
        return component.queryUtility(ISiteBrand)

    @Lazy
    def _brand_assets(self):
        return getattr(self._brand, 'assets', None)

    @Lazy
    def _brand_color(self):
        return getattr(self._brand, 'brand_color', None)

    @Lazy
    def _cert_brand_color(self):
        return getattr(self._brand, 'certificate_brand_color', None)

    @Lazy
    def _certificate_label(self):
        return getattr(self._brand, 'certificate_label', None)

    @Lazy
    def _suppress_logo(self):
        return getattr(self._brand, 'suppress_certificate_logo', False)

    def _brand_asset(self, name):
        asset = getattr(self._brand_assets, name, None)
        return getattr(asset, 'source', None)

    def add_image_utils_cleanup(self, img_utils):

        def after_commit_or_abort(_success=False):
            img_utils.cleanup()

        transaction.get().addAfterAbortHook(after_commit_or_abort)
        transaction.get().addAfterCommitHook(after_commit_or_abort)

    @Lazy
    def img_utils(self):
        img_utils = ImageUtils()
        self.add_image_utils_cleanup(img_utils)
        return img_utils

    def convert(self, input_file, width, height):
        if input_file.endswith(".svg"):
            return self.img_utils.convert(input_file, width, height)
        return input_file

    def constrain_size(self, input_file, max_width, max_height):
        if os.path.isfile(input_file):
            return self.img_utils.constrain_size(input_file, max_width, max_height)

        # To ensure we properly handle the conversion of any url-based
        # images, we'll need to retrieve them
        local_file, m = urllib.urlretrieve(input_file)
        try:
            ext = guess_extension(m.type)
            return self.img_utils.constrain_size(local_file,
                                                 max_width,
                                                 max_height,
                                                 format=ext[1:])
        finally:
            os.remove(local_file)

    def certificate_dict(self,
                         student_name,
                         provider_unique_id,
                         course_title,
                         completion_date_string,
                         facilitators=None,
                         credit=None):
        return {
            u'Brand': self._brand_name,
            u'Name': student_name,
            u'ProviderUniqueID': provider_unique_id,
            u'Course': course_title,
            u'Date': completion_date_string,
            u'Facilitators': facilitators or {},
            u'Credit': credit or (),
            u'CertificateLabel': self._certificate_label,
            u'CertificateSideBarImage':
                self._brand_asset('certificate_sidebar_image'),
            u'BrandLogo':
                self._brand_asset('certificate_logo') or self._brand_asset('logo'),
            u'BrandColor': self._cert_brand_color or self._brand_color,
            u'Converter': self.convert,
            u'ConstrainSize': self.constrain_size,
            u'SuppressLogo': self._suppress_logo,
            u'certificate_macro_name': self._certificate_renderer.macro_name
        }


@view_config(route_name='objects.generic.traversal',
             renderer="templates/completion_certificate.rml",
             request_method='GET',
             context=ICourseInstanceEnrollment,
             name=VIEW_CERTIFICATE,
             permission=nauth.ACT_READ)
class CompletionCertificateView(AbstractAuthenticatedView,
                                CompletionViewMixin,
                                EnrollmentProgressViewMixin):

    @Lazy
    def _certificate_renderer_name(self):
        """
        The named utility of the ICertificateRenderer to use. Drive this off
        of the course completion policy.
        """
        return self.course_policy.certificate_renderer_name

    @Lazy
    def course(self):
        # pylint: disable=no-member
        return self.context.CourseInstance

    @Lazy
    def user(self):
        # pylint: disable=no-member
        username = self.context.Username
        return User.get_user(username)

    @Lazy
    def _name(self):
        # A certificate is fairly formal so try and use realname first
        name = IFriendlyNamed(self.user).realname
        if not name:
            # Otherwise just fallback to whatever is our display name generator
            name = component.getMultiAdapter((self.user, self.request),
                                             IDisplayNameGenerator)()
        return name

    @Lazy
    def _course_completable_item(self):
        if self.course_policy is None:
            return None
        # pylint: disable=no-member
        return self.course_policy.is_complete(self.progress)

    def _filename(self, entry, suffix='completion', ext='pdf'):
        filename = '%s %s %s' % (self.user, entry.ProviderUniqueID, suffix)
        slugged = slugify(filename, seperator='_', lowercase=True)
        return '%s.%s' % (slugged, ext)

    @property
    def _completion_date_string(self):
        # pylint: disable=no-member
        completed = self._course_completable_item.CompletedDate
        tz_util = component.queryMultiAdapter((self.remoteUser, self.request),
                                              IDisplayableTimeProvider)
        completed = tz_util.adjust_date(completed)
        return completed.strftime('%B %d, %Y')

    def _facilitators(self, entry):
        facilitators = []
        for i in entry.Instructors:
            facilitator = {}
            for attr in ('Name', 'JobTitle'):
                facilitator[attr] = getattr(i, attr, '')
            facilitators.append(facilitator)
        return facilitators[:6]

    def _awarded_credit(self, transcript):
        if not transcript:
            return ()
        def _for_display(awarded_credit):
            return {
                u'Amount': u'%.2f' % awarded_credit.amount,
                u'Type': awarded_credit.credit_definition.credit_type,
                u'Units': awarded_credit.credit_definition.credit_units.capitalize()
            }
        return [_for_display(credit) for credit in transcript.iter_awarded_credits()]

    def __call__(self):
        # pylint: disable=no-member
        if     self._course_completable_item is None \
            or not self._course_completable_item.Success \
            or not self.course_policy.offers_completion_certificate:
            raise hexc.HTTPNotFound()

        entry = ICourseCatalogEntry(self.course)

        download = is_true(self.request.params.get('download', False))
        if download:
            response = self.request.response
            response.content_disposition = 'attachment; filename="%s"' % self._filename(entry)

        transcript = component.queryMultiAdapter((self.user, self.course),
                                                 ICreditTranscript)

        return self.certificate_dict(
            student_name=self._name,
            provider_unique_id=entry.ProviderUniqueID,
            course_title=entry.title,
            completion_date_string=self._completion_date_string,
            facilitators=self._facilitators(entry),
            credit=self._awarded_credit(transcript))


@view_config(route_name='objects.generic.traversal',
             renderer="templates/completion_certificate.rml",
             request_method='PUT',
             context=ISiteBrand,
             name=VIEW_CERTIFICATE_PREVIEW,
             permission=nauth.ACT_CONTENT_EDIT)
class CompletionCertificatePreview(CompletionViewMixin, SiteBrandUpdateBase):
    """
    This is effectively mixing the SiteBrand update view with the
    completion certificate view, so the user can see the effect of site
    brand updates on the certificate prior to persisting them.
    """
    
    def __init__(self, request):
        super(CompletionCertificatePreview, self).__init__(request)
        self._temp_sources = {}

    @Lazy
    def _certificate_renderer_name(self):
        """
        The named utility of the ICertificateRenderer to use. Use the given 
        query param or 'default'.
        """
        result = self.request.params.get('certificate_renderer_name', 'default')
        return result

    @property
    def _completion_date_string(self):
        completed = datetime.now()
        tz_util = component.queryMultiAdapter((self.remoteUser, self.request),
                                              IDisplayableTimeProvider)
        completed = tz_util.adjust_date(completed)
        return completed.strftime('%B %d, %Y')

    def add_post_transaction_cleanup(self, folder):

        def after_commit_or_abort(_success=False):
            shutil.rmtree(folder, ignore_errors=True)

        transaction.get().addAfterAbortHook(after_commit_or_abort)
        transaction.get().addAfterCommitHook(after_commit_or_abort)

    @Lazy
    def temp_folder(self):
        location_dir = tempfile.mkdtemp(prefix="completion_cert_preview")
        self.add_post_transaction_cleanup(location_dir)
        return location_dir

    def update_assets(self):
        """
        Store our temporary assets
        """
        if self._asset_url_dict or self._source_dict:
            # Ok, we have something
            location_dir = self.temp_folder

            # Handle external/url-based sources and removals
            for attr_name, asset_url in self._asset_url_dict.items():
                if not asset_url:
                    # Nulling out
                    self._temp_sources[attr_name] = None
                else:
                    self._temp_sources[attr_name] = asset_url

            # Handle local sources
            for attr_name, asset_file in self._source_dict.items():
                if attr_name not in self.ASSET_MULTIPART_KEYS:
                    continue

                try:
                    # Multipart upload
                    original_filename = asset_file.name
                except AttributeError:
                    # Source path
                    original_filename = os.path.split(asset_file)[-1]
                ext = os.path.splitext(original_filename)[1]
                filename = u'%s%s' % (attr_name, ext)
                path = os.path.join(location_dir, filename)
                self._copy_source_data(attr_name, asset_file, path, ext)
                self._temp_sources[attr_name] = path

    def _brand_asset(self, name):
        # If key exists in temp sources, use it (could be nulled out)
        if name in self._temp_sources:
            return self._temp_sources[name]

        return super(CompletionCertificatePreview, self)._brand_asset(name)

    def __call__(self):
        # Copy source attrs, import to do this before update
        if self._source_site_brand is not None:
            self._copy_source_brand_attrs(self._source_site_brand)
        UGDPutView.__call__(self)

        # Now update assets
        self.update_assets()

        # Essentially a preflight, so abandon changes
        transaction.doom()

        return self.certificate_dict(
            student_name=u"Sample Student",
            provider_unique_id=u"SMPL-1001",
            course_title=u"Sample Course",
            completion_date_string=self._completion_date_string,
            facilitators=[CourseCatalogInstructorInfo(
                Name=u"Sample Instructor",
                JobTitle=u"Instructor",
            )],
            credit=None)


@view_config(route_name='objects.generic.traversal',
             request_method='POST',
             context=ICourseInstanceEnrollment,
             name=VIEW_ACKNOWLEDGE_COMPLETION,
             permission=nauth.ACT_READ)
class AcknowledgeCompletionView(AbstractAuthenticatedView,
                                EnrollmentProgressViewMixin):

    def __call__(self):
        notification = ICourseCompletedNotification(self.context, None)
        if notification is None or notification.IsAcknowledged:
            raise hexc.HTTPNotFound()

        notification.acknowledge()

        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             request_method='DELETE',
             context=ICourseInstanceEnrollment,
             name=VIEW_ACKNOWLEDGE_COMPLETION,
             permission=nauth.ACT_UPDATE)
class DeleteCompletionAckView(AbstractAuthenticatedView,
                              EnrollmentProgressViewMixin):

    def __call__(self):
        notification = ICourseCompletedNotification(self.context, None)
        if notification is None or not notification.IsAcknowledged:
            raise hexc.HTTPNotFound()

        notification.reset_acknowledgement()

        return hexc.HTTPNoContent()

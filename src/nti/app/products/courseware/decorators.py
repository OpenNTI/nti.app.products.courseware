#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from six.moves.urllib_parse import urljoin

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from pyramid.threadlocal import get_current_request

from nti.app.assessment.common.evaluations import is_global_evaluation
from nti.app.assessment.common.evaluations import get_course_from_evaluation

from nti.app.assessment.utils import get_course_from_request

from nti.app.products.courseware import VIEW_CONTENTS
from nti.app.products.courseware import VIEW_COURSE_MAIL
from nti.app.products.courseware import VIEW_CATALOG_ENTRY
from nti.app.products.courseware import VIEW_COURSE_BY_TAG
from nti.app.products.courseware import VIEW_COURSE_ACTIVITY
from nti.app.products.courseware import VIEW_USER_ENROLLMENTS
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE
from nti.app.products.courseware import VIEW_COURSE_CLASSMATES
from nti.app.products.courseware import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware import VIEW_LESSONS_CONTAINERS
from nti.app.products.courseware import VIEW_ENROLLMENT_OPTIONS
from nti.app.products.courseware import VIEW_RECURSIVE_AUDIT_LOG
from nti.app.products.courseware import VIEW_COURSE_LOCKED_OBJECTS
from nti.app.products.courseware import VIEW_COURSE_TAB_PREFERENCES
from nti.app.products.courseware import VIEW_COURSE_RECURSIVE_BUCKET
from nti.app.products.courseware import VIEW_COURSE_CATALOG_FAMILIES
from nti.app.products.courseware import VIEW_COURSE_ENROLLMENT_ROSTER

from nti.app.products.courseware.interfaces import ACT_VIEW_ACTIVITY

from nti.app.products.courseware.interfaces import IOpenEnrollmentOption
from nti.app.products.courseware.interfaces import IExternalEnrollmentOption
from nti.app.products.courseware.interfaces import ICoursesCatalogCollection
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICourseTabConfigurationUtility

from nti.app.products.courseware.utils import get_enrollment_options
from nti.app.products.courseware.utils import get_evaluation_lessons
from nti.app.products.courseware.utils import get_vendor_thank_you_page
from nti.app.products.courseware.utils import get_content_related_work_refs
from nti.app.products.courseware.utils import PreviewCourseAccessPredicateDecorator

from nti.app.renderers.decorators import AbstractRequestAwareDecorator
from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.pyramid_renderers_edit_link_decorator import LinkRemoverDecorator

from nti.appserver.workspaces import VIEW_CATALOG_POPULAR
from nti.appserver.workspaces import VIEW_CATALOG_FEATURED

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.common.hash import md5_base64_digest

from nti.contentlibrary.interfaces import IEditableContentUnit

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstanceScopedForum

from nti.contenttypes.courses.sharing import get_default_sharing_scope

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import has_enrollments
from nti.contenttypes.courses.utils import get_catalog_entry
from nti.contenttypes.courses.utils import is_course_instructor
from nti.contenttypes.courses.utils import get_enrollment_record
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import is_course_instructor_or_editor
from nti.contenttypes.courses.utils import get_context_enrollment_records

from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef

from nti.coremetadata.interfaces import ILastSeenProvider

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.contenttypes.forums.interfaces import ITopic

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IEntityContainer
from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.externalization.singleton import Singleton

from nti.links.links import Link

from nti.links.externalization import render_link

from nti.mimetype.mimetype import nti_mimetype_from_object

from nti.ntiids.ntiids import make_specific_safe

from nti.ntiids.oids import to_external_ntiid_oid

from nti.traversal.traversal import find_interface

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
MIMETYPE = StandardExternalFields.MIMETYPE

COURSE_CONTEXT_ANNOT_KEY = 'nti.app.products.course.context_key'

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceLinkDecorator(Singleton):
    """
    If a course instance can find its catalog entry, return that as a link.
    Also make it return an href, even if it isn't top-level.
    """

    def decorateExternalMapping(self, context, result):
        # We have no way to know what order these will be
        # called in, so we must preserve anything that exists
        _links = result.setdefault(LINKS, [])
        entry = ICourseCatalogEntry(context, None)
        if entry:
            _links.append(Link(entry, rel=VIEW_CATALOG_ENTRY))

        for rel in (VIEW_USER_COURSE_ACCESS, VIEW_COURSE_CATALOG_FAMILIES):
            link = Link(context, rel=rel, elements=('@@%s' % rel,))
            _links.append(link)

        request = get_current_request()
        if request is not None and has_permission(ACT_VIEW_ACTIVITY, context, request):
            # Give instructors the enrollment roster, activity, and mail links.
            # NOTE: Assuming the two permissions are concordant; at worst this is a UI
            # issue though, the actual views are protected with individual
            # permissions
            for rel in VIEW_COURSE_ENROLLMENT_ROSTER, VIEW_COURSE_ACTIVITY:
                _links.append(Link(context,
                                   rel=rel,
                                   elements=(rel,)))

        if 'href' not in result:
            link = Link(context)
            interface.alsoProvides(link, ILinkExternalHrefOnly)
            result['href'] = link


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _EntryHrefDecorator(Singleton):
    """
    Decorate :class:`ICourseCatalogEntry` objects with hrefs, if needed. These
    typically get added already via the IRecordable interface.
    """

    def decorateExternalObject(self, context, result):
        if 'href' not in result:
            link = Link(context)
            interface.alsoProvides(link, ILinkExternalHrefOnly)
            result['href'] = link

@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _RealPreviewDecorator(Singleton):

    def decorateExternalMapping(self, context, result):
        if hasattr(context, 'PreviewRawValue'):
            result['PreviewRawValue'] = context.PreviewRawValue


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CourseEnrollmentDecorator(Singleton):
    """
    Decorates the enrollment stats (XXX That may be really slow.)
    """

    def decorateExternalMapping(self, context, result):
        course = ICourseInstance(context)
        enrollments = ICourseEnrollments(course)
        result['TotalEnrolledCount'] = enrollments.count_enrollments()


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseMailLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the course email link on the course for instructors.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and is_course_instructor(context, self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_COURSE_MAIL,
                    elements=(VIEW_COURSE_MAIL,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


class BaseRecursiveAuditLogLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the audit log links on the given context if the
    remote user has edit permissions.
    """

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
           and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name in (VIEW_RECURSIVE_AUDIT_LOG, VIEW_COURSE_LOCKED_OBJECTS):
            link = Link(context, rel=name, elements=('@@%s' % name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class CourseRecursiveAuditLogLinkDecorator(BaseRecursiveAuditLogLinkDecorator):
    pass


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _RosterMailLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the course email link on the roster record for instructors.
    """

    def _predicate(self, context, unused_result):
        if not self._is_authenticated:
            return False
        course = ICourseInstance(context, None)
        return course is not None \
           and IUser(context, None) is not None \
           and is_course_instructor(course, self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_COURSE_MAIL,
                    elements=(VIEW_COURSE_MAIL,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _VendorThankYouInfoDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the thank you page information.
    """

    def _do_decorate_external(self, context, result):
        course = ICourseInstance(context)
        key = getattr(context, 'RealEnrollmentStatus', None)
        if course is not None and key:
            thank_you_page = get_vendor_thank_you_page(course, key)
            if thank_you_page:
                result['VendorThankYouPage'] = thank_you_page


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceStreamLinkDecorator(Singleton):
    """
    Place the recursive stream links on the course.
    """

    def decorateExternalMapping(self, context, result):
        _links = result.setdefault(LINKS, [])
        for name in (VIEW_COURSE_RECURSIVE, VIEW_COURSE_RECURSIVE_BUCKET):
            link = Link(context, rel=name, elements=(name,))
            interface.alsoProvides(link, ILocation)
            link.__name__ = ''
            link.__parent__ = context
            _links.append(link)


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseTabPreferencesLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _can_read(self, context):
        return has_permission(ACT_READ, context, self.request)

    def _can_edit(self, context):
        config = component.queryUtility(ICourseTabConfigurationUtility)
        return config and config.can_edit_tabs(self.remoteUser, context)

    def _make_link(self, context, rel, method):
        link = Link(context,
                    rel=rel,
                    elements=(VIEW_COURSE_TAB_PREFERENCES,),
                    method=method)
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        return link

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        if self._can_read(context):
            _links.append(self._make_link(context,
                                          'GetCourseTabPreferences',
                                          'GET'))

        if self._can_edit(context):
            _links.append(self._make_link(context,
                                          'UpdateCourseTabPreferences',
                                          'PUT'))


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstancePagesLinkDecorator(PreviewCourseAccessPredicateDecorator):
    """
    Places a link to the pages view of a course.
    """

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel='Pages', elements=('Pages',))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@component.adapter(ICourseOutline)
@interface.implementer(IExternalMappingDecorator)
class _CourseOutlineContentsLinkDecorator(PreviewCourseAccessPredicateDecorator):
    """
    Adds the Contents link to the course outline to fetch its children.
    """

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_CONTENTS, elements=(VIEW_CONTENTS,),
                    params={'omit_unpublished': True})
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


_LEGACY_INLINE_COURSE_UA = u'NTIFoundation DataLoader NextThought'

@interface.implementer(IExternalMappingDecorator)
class _CourseWrapperLinkDecorator(Singleton):
    """
    Because we are now typically waking up the user profile from the
    database *anyway* when we request enrollment rosters (to sort on),
    it's relatively cheap and useful to the (current) UI to send back
    some extra details.
    """

    def _request_needs_inline_instance(self, request):
        ua = request.environ.get('HTTP_USER_AGENT', '')
        return _LEGACY_INLINE_COURSE_UA in ua

    def _should_inline_instance(self, context):
        # TODO: Once the apps aren't relying on the inlined info
        # tweak this predicate.  Be sure for ipad (non updated apps)
        # we continue to inline for bwc.
        request = get_current_request()
        inline = self._request_needs_inline_instance(request)
        return inline and getattr(context, 'CourseInstance', None) is not None

    def _should_inline_entry(self, context):
        # Action at a distance here, but piggy back off the fact
        # that if we don't have an Instance set (someone nulled it out)
        # for perf reasons (i.e. roster) we probably also don't want
        # the catalog
        return getattr(context, 'CourseInstance', None) is not None

    def decorateExternalMapping(self, context, result):
        course = ICourseInstance(context, None)
        entry = ICourseCatalogEntry(course, None)

        if hasattr(entry, 'ntiid'):
            result['CatalogEntryNTIID'] = entry.ntiid

        _links = result.setdefault(LINKS, [])

        if entry:
            _links.append( Link(entry, rel=VIEW_CATALOG_ENTRY) )
        if course:
            _links.append( Link(course,
                                rel='CourseInstance',
                                target_mime_type=nti_mimetype_from_object(course)) )

        # In the past we inlined the CourseInstance on these objects.
        # This turns out to be very expensive and not all that useful in the
        # majority of cases clients are consuming these objects.  They're
        # most often showed in lists/grids as entrance points of the course.
        # We'd much rather make that fast and defer the rendering/fetching of
        # the course instance until needed (via the link).  We no longer
        # externalize that by default (which is a backwords incompatible change) so restore it here
        # in a conditional decorator. 2018-03-13 -cutz
        if 'CourseInstance' not in result:
            result['CourseInstance'] = course if self._should_inline_instance(context) else None

        # On the other hand it is useful in the majority of cases (everyhwere but the
        # roster) to inline the CatalogEntry.  Inline that here also.
        if 'CatalogEntry' not in result:
            result['CatalogEntry'] = entry if self._should_inline_entry(context) else None


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CourseCatalogEntryLegacyDecorator(Singleton):
    """
    Restore some legacy fields used by existing applications.
    """

    def decorateExternalMapping(self, context, result):
        result['Title'] = context.title
        result['Description'] = context.description


@component.adapter(IOpenEnrollmentOption)
@interface.implementer(IExternalObjectDecorator)
class _OpenEnrollmentOptionLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return self._is_authenticated

    @classmethod
    def _get_enrollment_record(cls, context, remoteUser):
        entry = get_catalog_entry(context.CatalogEntryNTIID)
        return get_enrollment_record(entry, remoteUser)

    def _do_decorate_external(self, context, result):
        record = self._get_enrollment_record(context, self.remoteUser)
        result['IsAvailable'] = context.Enabled and record is None
        result['IsEnrolled'] = bool(record is not None
                                    and record.Scope == ES_PUBLIC)


@component.adapter(IExternalEnrollmentOption)
@interface.implementer(IExternalObjectDecorator)
class _ExternalEnrollmentOptionLinkDecorator(_OpenEnrollmentOptionLinkDecorator):

    def _do_decorate_external(self, context, result):
        record = self._get_enrollment_record(context, self.remoteUser)
        result['IsAvailable'] = record is None
        result['IsEnrolled'] = bool(record is not None
                                    and record.Scope == ES_PURCHASED)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CourseCatalogEntryDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, unused_context, unused_result):
        return self._is_authenticated

    def _get_legacy_status(self, record):
        enrollment = ICourseInstanceEnrollment(record)
        return getattr(enrollment, 'LegacyEnrollmentStatus', '')

    def _is_admin(self, entry):
        # Decorated admin status is only if the user is a course instructor
        # or editor.
        course = ICourseInstance(entry)
        result = is_course_instructor_or_editor(course, self.remoteUser)
        return bool(result)

    def _do_decorate_external(self, context, result):
        record = get_enrollment_record(context, self.remoteUser)
        is_admin = False
        if record is not None:
            result['RealEnrollmentStatus'] = record.Scope
            legacy_status = self._get_legacy_status(record)
            result['LegacyEnrollmentStatus'] = legacy_status
        else:
            is_admin = self._is_admin(context)
        result['IsEnrolled'] = record is not None
        result['IsAdmin'] = is_admin

        options = get_enrollment_options(context)
        if options:
            result[u'EnrollmentOptions'] = to_external_object(options)

        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_USER_COURSE_ACCESS,
                    elements=('@@%s' % VIEW_USER_COURSE_ACCESS,))
        _links.append(link)


@interface.implementer(IExternalMappingDecorator)
class _BaseClassmatesLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context, rel=VIEW_COURSE_CLASSMATES,
                    elements=(VIEW_COURSE_CLASSMATES,))
        interface.alsoProvides(link, ILocation)
        link.__name__ = ''
        link.__parent__ = context
        _links.append(link)


@interface.implementer(IExternalMappingDecorator)
class _CourseClassmatesLinkDecorator(_BaseClassmatesLinkDecorator):

    def _predicate(self, context, unused_result):
        result = bool(self._is_authenticated and is_enrolled(
            context, self.remoteUser))
        return result


@component.adapter(IUser)
class _ClassmatesLinkDecorator(_BaseClassmatesLinkDecorator):

    def _predicate(self, context, unused_result):
        result = self._is_authenticated \
             and self.remoteUser == context \
             and has_enrollments(self.remoteUser)
        return result


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CatalogFamilyDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Expose the catalog family for a course catalog entry.
    """
    class_name = 'CatalogFamilies'
    family_display_fields = ('ProviderUniqueID',
                             'ProviderDepartmentTitle',
                             'StartDate',
                             'EndDate',
                             'Title',
                             'Description',
                             'PlatformPresentationResources')

    def _predicate(self, context, unused_result):
        """
        Only return a catalog entry family for course subinstances
        or course super instances.
        """
        context = ICourseInstance(context, None)
        subinstances = get_course_subinstances(context)
        return ICourseSubInstance.providedBy(context) or subinstances

    def _build_catalog_family(self, super_catalog):
        catalog_family = {}
        catalog_family[CLASS] = 'CatalogFamily'
        catalog_family[MIMETYPE] = 'application/vnd.nextthought.catalogfamily'
        # Return opaque family ID.
        catalog_family['CatalogFamilyID'] = md5_base64_digest(
            str(super_catalog.ntiid))
        for field in self.family_display_fields:
            val = getattr(super_catalog, field, None)
            if val is not None:
                catalog_family[field] = val
        return catalog_family

    def _do_decorate_external(self, context, result):
        course = ICourseInstance(context, None)
        if ICourseSubInstance.providedBy(course):
            course = course.__parent__.__parent__
        super_catalog = ICourseCatalogEntry(course, None)
        if super_catalog is not None:
            catalog_families = {}
            catalog_families[CLASS] = self.class_name
            catalog_families[MIMETYPE] = 'application/vnd.nextthought.catalogfamilies'
            catalog_families[ITEMS] = vals = []

            # We support a list of catalog families, but we only
            # provide the super course catalog entry for now.
            catalog_family = self._build_catalog_family(super_catalog)
            vals.append(catalog_family)

            result[self.class_name] = catalog_families

        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_COURSE_CATALOG_FAMILIES,
                    elements=('@@%s' % VIEW_COURSE_CATALOG_FAMILIES,))
        _links.append(link)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance, interface.Interface)
class _SharingScopesAndDiscussionDecorator(PreviewCourseAccessPredicateDecorator,
                                           AbstractAuthenticatedRequestAwareDecorator):

    def _predicate(self, context, result):
        return self._is_authenticated \
           and super(_SharingScopesAndDiscussionDecorator, self)._predicate(context, result)

    def _do_decorate_external(self, context, result):
        is_section = ICourseSubInstance.providedBy(context)

        default_scope = get_default_sharing_scope(context)
        default_sharing_scope_ntiid = getattr(default_scope, 'NTIID', None)

        if is_section:
            # conflated, yes, but simpler
            parent = context.__parent__.__parent__
            if parent is not None:
                parent_result = {}
                self._do_decorate_external(parent, parent_result)
                result['ParentLegacyScopes'] = parent_result.get(
                    'LegacyScopes')
                result['ParentSharingScopes'] = parent_result['SharingScopes']
                result['ParentDiscussions'] = to_external_object(parent.Discussions,
                                                                 request=self.request)

        scopes = context.SharingScopes
        ext_scopes = LocatedExternalDict()
        ext_scopes.__name__ = scopes.__name__
        ext_scopes.__parent__ = scopes.__parent__
        ext_scopes[MIMETYPE] = scopes.mime_type

        ext_scopes[CLASS] = 'CourseInstanceSharingScopes'
        items = ext_scopes[ITEMS] = {}

        user = self.remoteUser if self._is_authenticated else None
        for name, scope in scopes.items():
            if user is None or user in IEntityContainer(scope):
                items[name] = to_external_object(scope, request=self.request)

        result['SharingScopes'] = ext_scopes

        # Legacy
        if 'LegacyScopes' not in result:
            ls = result['LegacyScopes'] = {}
            # Historically, you get public and restricted regardless of whether
            # you were enrolled in them...
            # Because we're talking specifically to legacy clients, we need to give them
            # something that makes sense in their flat view of the world; therefore,
            # if we're actually in a subinstance, we want public sharing to be TRULY
            # public, across everyone that might be enrolled in all sections. The exception
            # is if the parent course is non-open-enrollable (e.g., closed, or not being used
            # except for administration---one scenario had two sections that opened at different
            # dates); in that case, we want to use the parent if we can get it.
            if default_sharing_scope_ntiid is not None:
                public = default_sharing_scope_ntiid
            else:
                public = None
                parent = context.__parent__
                if (is_section
                    and find_interface(parent, INonPublicCourseInstance, strict=False) is None
                        and 'public' in result.get('ParentLegacyScopes', ())):
                    public = result['ParentLegacyScopes']['public']
                elif ES_PUBLIC in scopes:
                    public = scopes[ES_PUBLIC].NTIID

            ls['public'] = public

            if ES_CREDIT in scopes:
                ls['restricted'] = scopes[ES_CREDIT].NTIID
            if ES_PURCHASED in scopes:
                ls['purchased'] = scopes[ES_PURCHASED].NTIID

        ls = result['LegacyScopes']

        if default_sharing_scope_ntiid is None:
            # Point clients to what the should do by default.
            # For the default if you're not enrolled for credit, match what
            # flat clients do.
            default_sharing_scope_ntiid = ls['public']
            if user is not None and not is_course_instructor(context, user):
                if ES_CREDIT in scopes and user in IEntityContainer(scopes[ES_CREDIT]):
                    default_sharing_scope_ntiid = ls.get('restricted')
                elif ES_PURCHASED in scopes and user in IEntityContainer(scopes[ES_PURCHASED]):
                    default_sharing_scope_ntiid = ls.get('purchased')

        result['SharingScopes']['DefaultSharingScopeNTIID'] = default_sharing_scope_ntiid


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstance, interface.Interface)
class _AnnouncementsDecorator(PreviewCourseAccessPredicateDecorator,
                              AbstractAuthenticatedRequestAwareDecorator):
    """
    Adds announcement discussions to externalized course, by scope.
    """

    def _predicate(self, context, result):
        return self._is_authenticated \
           and super(_AnnouncementsDecorator, self)._predicate(context, result)

    def _in_scope(self, scope_name, course):
        user = self.remoteUser if self._is_authenticated else None
        scope = course.SharingScopes[scope_name]
        # In scope if we have user and they are in scope.
        return user is not None and user in IEntityContainer(scope)

    def _get_forum_key(self, forum_types, name, display_key):
        result = forum_types.get(display_key)
        if not result:
            # Replicate forum key logic used during create time
            result = make_specific_safe(name + ' ' + 'Announcements')
        return result

    def _do_decorate_external(self, context, result):

        # First, get parent if we are a section.
        is_section = ICourseSubInstance.providedBy(context)

        if is_section:
            # conflated, yes, but simpler
            parent = context.__parent__.__parent__
            if parent is not None:
                parent_result = {}
                self._do_decorate_external(parent, parent_result)
                result['ParentAnnouncementForums'] = parent_result.get(
                    'AnnouncementForums')

        # A marker interface might make this easier
        announcements = {}
        items = {ITEMS: announcements,
                 CLASS: 'CourseInstanceAnnouncementForums'}

        vendor_info = ICourseInstanceVendorInfo(context)
        forum_types = vendor_info.get('NTI', {}).get('Forums', {})

        for scope_name, scope_term in ENROLLMENT_SCOPE_VOCABULARY.by_token.iteritems():
            name = scope_term.vendor_key
            key_prefix = scope_term.vendor_key_prefix

            has_key = 'Has' + key_prefix + 'Announcements'

            # They have announcements and we're in the scope
            if forum_types.get(has_key) and self._in_scope(scope_name, context):
                # Ok, let's find our forum
                display_key = key_prefix + 'AnnouncementsDisplayName'
                forum_key = self._get_forum_key(forum_types, name, display_key)

                discussions = context.Discussions
                found_forum = discussions.get(forum_key)
                if found_forum is not None:
                    announcements[scope_name] = found_forum

        if announcements:
            result['AnnouncementForums'] = items


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _CourseCatalogEntryProviderDecorator(Singleton):

    def decorateExternalObject(self, context, result):
        result['ProviderDisplayName'] = context.ProviderUniqueID
        result.pop('DisplayName', None)  # replace for legacy purposes


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstanceEnrollmentDecorator(Singleton):

    def decorateExternalObject(self, context, result):
        if IUser(context, None) is not None:
            context_link = Link(context)
            interface.alsoProvides(context_link, ILinkExternalHrefOnly)
            result['href'] = render_link(context_link)


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _CourseInstanceEnrollmentLastSeenDecorator(AbstractRequestAwareDecorator):

    def _do_decorate_external(self, context, result):
        if 'LastSeenTime' not in result:
            user = IUser(context, None)
            inst = ICourseInstance(context, None)
            provider = component.queryMultiAdapter((user, inst), ILastSeenProvider)
            result['LastSeenTime'] = provider.lastSeenTime if provider else None


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class _LegacyCCEFieldDecorator(Singleton):

    def _course_package(self, context):
        course = ICourseInstance(context, None)
        for package in get_course_packages(context):
            if not IEditableContentUnit.providedBy(package):
                return course, package
        return course, None

    def _content_bundle(self, context):
        course = ICourseInstance(context, None)
        try:
            return course.ContentPackageBundle
        except AttributeError:  # pragma: no cover
            return None

    def decorateExternalObject(self, context, result):
        # All the possibly missing legacy fields hang off
        # an existing single content package. Can we get one of those?
        course = None
        package = None
        checked = False

        if 'ContentPackageBundleNTIID' not in result:
            bundle = self._content_bundle(context)
            if bundle is not None and getattr(bundle, 'ntiid', None):
                result['ContentPackageBundleNTIID'] = bundle.ntiid

        if 'ContentPackageNTIID' not in result:
            course, package = self._course_package(context)
            checked = True
            if package is not None:
                result['ContentPackageNTIID'] = package.ntiid

        if     not result.get('LegacyPurchasableIcon') \
            or not result.get('LegacyPurchasableThumbnail'):

            if not checked:
                course, package = self._course_package(context)
                checked = True

            if package is not None:
                # Copied wholesale from legacy code
                purch_id = context.ProviderUniqueID or ''
                purch_id = purch_id.replace(' ', '').split('-')[0]
                # non interface, briefly seen field
                if purch_id and getattr(context, 'Term', ''):
                    purch_id += context.Term.replace(' ', '').replace('-', '')

                # We have to externalize the package to get correct URLs to
                # the course. They need to be absolute because there is no context
                # in the purchasable.
                ext_package = to_external_object(package)
                # Make sure the package has info
                if 'href' in ext_package and purch_id:
                    icon = urljoin(ext_package['href'],
                                   'images/' + purch_id + '_promo.png')
                    thumbnail = urljoin(ext_package['href'],
                                        'images/' + purch_id + '_cover.png')
                    # Temporarily also stash these things on the entry itself too
                    # where they can be externalized in the course catalog;
                    # this should save us a trip through next time
                    context.LegacyPurchasableIcon = icon
                    context.LegacyPurchasableThumbnail = thumbnail

                    result['LegacyPurchasableIcon'] = icon
                    result['LegacyPurchasableThumbnail'] = thumbnail

        if 'CourseNTIID' not in result:
            if not checked:
                course, package = self._course_package(context)
                checked = True
            if course is not None:
                # courses themselves do not typically actually
                # have an identifiable NTIID and rely on the OID
                # (this might change with auto-creation of the catalogs now)
                try:
                    result['CourseNTIID'] = course.ntiid
                except AttributeError:
                    result['CourseNTIID'] = to_external_ntiid_oid(course)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICourseInstanceScopedForum, interface.Interface)
class _SharedScopesForumDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Puts the type of forum into the discussion.
    """

    def _do_decorate_external(self, context, result):
        # Allow for native externalization, and copy to AutoTags;
        # this will assist with class evolution...AutoTags is visible
        # before people update their models
        scope_name = result.get('SharingScopeName')
        if not scope_name:
            scope_name = getattr(context, 'SharingScopeName', None)
        if not scope_name:
            # Ok, is it on the tagged value?
            provided_by = interface.providedBy(context)
            scope_name = provided_by.get(
                'SharingScopeName').queryTaggedValue('value')

        if scope_name:
            result.setdefault('AutoTags', []).append(
                'SharingScopeName=' + scope_name)
            result['SharingScopeName'] = scope_name


@component.adapter(ICourseInstance)
@interface.implementer(IExternalObjectDecorator)
class _CourseInstancePreviewExcludingDecorator(PreviewCourseAccessPredicateDecorator):
    """
    Removes external entries that should not be visible to a user
    when the context is in preview mode.
    """

    def _predicate(self, context, result):
        # We only want to pop entries if the predicate is False.
        return not super(_CourseInstancePreviewExcludingDecorator, self)._predicate(context, result)

    def _do_decorate_external(self, unused_context, result):
        result.pop('Discussions', None)


@component.adapter(ITopic)
@interface.implementer(IExternalObjectDecorator)
class TopicAddRemoverLinkDecorator(LinkRemoverDecorator):
    """
    Remove add link if not instructor but has course content edit perms
    """

    links_to_remove = ('add',)

    def _predicate(self, context, unused_result):
        course = find_interface(context, ICourseInstance, strict=False)
        return self._is_authenticated \
           and course is not None \
           and not is_course_instructor(course, self.remoteUser) \
           and has_permission(ACT_CONTENT_EDIT, course, self.request)


class _AbstractLessonsContainerDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Add a lessons link to fetch all lessons containing our given
    assessment context and add a `LessonContainerCount`.
    """

    def _get_lessons(self, context):
        raise NotImplementedError()

    def _predicate(self, context, unused_result):
        return self._is_authenticated \
            and has_permission(ACT_CONTENT_EDIT, context, self.request)

    def _get_link(self, context):
        link = Link(context,
                    rel=VIEW_LESSONS_CONTAINERS,
                    elements=('@@%s' % VIEW_LESSONS_CONTAINERS,))
        return link

    def _do_decorate_external(self, context, result):
        lessons = self._get_lessons(context)
        result['LessonContainerCount'] = len(lessons or ())
        link = self._get_link(context)
        _links = result.setdefault(LINKS, [])
        _links.append(link)


# XXX: For now, only editable content units can be shared.
@component.adapter(IEditableContentUnit)
@interface.implementer(IExternalObjectDecorator)
class _ContentUnitLessonsContainerDecorator(_AbstractLessonsContainerDecorator):

    def _get_lessons(self, context):
        return get_content_related_work_refs(context)


class _AbstractAssessmentLessonsContainerDecorator(_AbstractLessonsContainerDecorator):

    #: Subclasses need to define which outline ref they need to look up.
    provided = None

    def _get_course(self, evaluation):
        result = get_course_from_request(self.request)
        if result is None:
            result = get_course_from_evaluation(evaluation=evaluation,
                                                user=self.remoteUser)
        return result

    def _predicate(self, context, result):
        return not is_global_evaluation(context) \
            and super(_AbstractAssessmentLessonsContainerDecorator, self)._predicate(context, result)

    def _get_lessons(self, context):
        return get_evaluation_lessons(context, self.provided)

    def _get_link(self, context):
        course = self._get_course(context)
        link_context = context if course is None else course
        pre_elements = () if course is None else ('Assessments', context.ntiid)
        link = Link(link_context,
                    rel=VIEW_LESSONS_CONTAINERS,
                    elements=pre_elements + ('@@%s' % VIEW_LESSONS_CONTAINERS,))
        return link


@component.adapter(IQuestionSet)
@interface.implementer(IExternalObjectDecorator)
class QuestionSetLessonsContainerDecorator(_AbstractAssessmentLessonsContainerDecorator):
    provided = INTIQuestionSetRef


@component.adapter(IQAssignment)
@interface.implementer(IExternalObjectDecorator)
class AssignmentLessonsContainerDecorator(_AbstractAssessmentLessonsContainerDecorator):
    provided = (INTIAssignmentRef, INTIQuestionSetRef)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICoursesCatalogCollection)
class _PopularCourseCatalogCollectionDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:``ICoursesCatalogCollection``.
    """

    def _predicate(self, context, unused_result):
        return len(context)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_CATALOG_POPULAR,
                    elements=('@@%s' % VIEW_CATALOG_POPULAR,))
        _links.append(link)


@interface.implementer(IExternalObjectDecorator)
@component.adapter(ICoursesCatalogCollection)
class _CourseCatalogCollectionDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:``ICoursesCatalogCollection``.
    """

    def _predicate(self, context, unused_result):
        return len(context)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        for rel in (VIEW_CATALOG_FEATURED,
                    VIEW_COURSE_BY_TAG):
            link = Link(context,
                        rel=rel,
                        elements=('@@%s' % rel,))
            _links.append(link)


@component.adapter(IUser)
@interface.implementer(IExternalObjectDecorator)
class _UserEnrollmentsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorate the :class:``IUser``.
    """

    def _predicate(self, context, unused_result):
        return get_context_enrollment_records(context, self.remoteUser)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        link = Link(context,
                    rel=VIEW_USER_ENROLLMENTS,
                    elements=('@@%s' % VIEW_USER_ENROLLMENTS,))
        _links.append(link)


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalObjectDecorator)
class AdminCatalogEntryDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Allow editors to attach :class:`IEnrollmentOption` objects to a course.
    """

    def _predicate(self, context, unused_result):
        course = ICourseInstance(context, None)
        if course is not None:
            return has_permission(ACT_CONTENT_EDIT, course, self.request)

    def _do_decorate_external(self, context, result):
        course = ICourseInstance(context)
        _links = result.setdefault(LINKS, [])
        link = Link(course,
                    rel=VIEW_ENROLLMENT_OPTIONS,
                    method='PUT',
                    elements=(VIEW_ENROLLMENT_OPTIONS,))
        _links.append(link)

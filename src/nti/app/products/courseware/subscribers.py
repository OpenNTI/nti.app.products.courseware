#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os
import time
import isodate
import datetime

from pyramid.threadlocal import get_current_request

from zc.intid.interfaces import IAfterIdAddedEvent
from zc.intid.interfaces import IBeforeIdRemovedEvent

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.cachedescriptors.property import Lazy

from zope.component.hooks import getSite

from zope.dottedname import resolve as dottedname

from zope.event import notify

from zope.i18n import translate

from zope.lifecycleevent.interfaces import IObjectAddedEvent
from zope.lifecycleevent.interfaces import IObjectCreatedEvent
from zope.lifecycleevent.interfaces import IObjectModifiedEvent

from zope.publisher.interfaces.browser import IBrowserRequest

from zope.security.interfaces import IPrincipal
from zope.security.management import endInteraction
from zope.security.management import queryInteraction
from zope.security.management import restoreInteraction

from zope.site.interfaces import INewLocalSite

from zope.traversing.interfaces import IBeforeTraverseEvent

from nti.app.authentication import get_remote_user

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware import USER_ENROLLMENT_LAST_MODIFIED_KEY
from nti.app.products.courseware import SITE_ADMIN_SHARING_SCOPES_PRINCIPAL_STR

from nti.app.products.courseware.interfaces import ICourseSharingScopeUtility
from nti.app.products.courseware.interfaces import ICourseEnrollmentEmailBCCProvider
from nti.app.products.courseware.interfaces import ICourseEnrollmentEmailArgsProvider

from nti.app.products.courseware.sharing_scopes import CourseSharingScopeUtility

from nti.app.products.courseware.utils import get_enrollment_courses
from nti.app.products.courseware.utils import get_enrollment_for_scope
from nti.app.products.courseware.utils import get_enrollment_communities

from nti.app.site.interfaces import ISiteAdminAddedEvent
from nti.app.site.interfaces import ISiteAdminRemovedEvent

from nti.app.users.utils import get_site_admins

from nti.appserver.brand.utils import get_site_brand_name

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contentlibrary.interfaces import IContentBundleUpdatedEvent

from nti.contenttypes.courses.common import get_course_site_name

from nti.contenttypes.courses.interfaces import ES_PUBLIC

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseContentPackageBundle
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent

from nti.contenttypes.courses.utils import get_parent_course
from nti.contenttypes.courses.utils import get_course_hierarchy

from nti.coremetadata.interfaces import UserLastSeenEvent
from nti.coremetadata.interfaces import ISupplementalACLProvider
from nti.coremetadata.interfaces import IShareableModeledContent

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization import is_site_admin

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IGroupMember

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IEmailAddressable

from nti.dataserver.users.entity import Entity

from nti.externalization.externalization import to_external_object

from nti.mailer.interfaces import ITemplatedMailer

from nti.ntiids.ntiids import find_object_with_ntiid, is_valid_ntiid_string

from nti.site.interfaces import IHostPolicySiteManager

from nti.site.localutility import install_utility

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


# Email


def _get_template(catalog_entry,
                  base_template='enrollment_confirmation_email',
                  package='nti.app.products.courseware'):
    """
    Look for course-specific templates, if available.
    """
    result = None
    package = dottedname.resolve(package)
    catalog_entry = ICourseCatalogEntry(catalog_entry)
    for provider in (catalog_entry.ProviderUniqueID, catalog_entry.DisplayName):
        if not provider:
            continue
        provider = provider.replace(' ', '').lower()
        replaced_provider = provider.replace('-', '')
        template = replaced_provider + "_" + base_template
        path = os.path.join(os.path.dirname(package.__file__), 'templates')
        if not os.path.exists(os.path.join(path, template + ".pt")):
            # Full path doesn't exist; drop our specific id part and try that
            # 'EDMA 4970', 'EDMA 4970-995', EDMA 4970/5970-995'
            provider_prefix = provider.split('-')[0]
            provider_prefix = provider_prefix.split('/')[0]
            template = provider_prefix + "_" + base_template
            if os.path.exists(os.path.join(path, template + ".pt")):
                result = template
                break
        else:
            result = template
            break
    return result or base_template
get_course_template = _get_template


def _send_enrollment_confirmation(event, user, profile, email, course):
    # Note that the `course` is an nti.contenttypes.courses.ICourseInstance

    # Can only do this in the context of a user actually
    # doing something; we need the request for locale information
    # as well as URL information.
    request = getattr(event, 'request', get_current_request())
    if not request or not email:
        logger.warning("Not sending an enrollment email to %s because of no email or request",
                       user)
        return

    policy = component.getUtility(ISitePolicyUserEventListener)

    assert getattr(IEmailAddressable(profile, None), 'email', None) == email
    assert getattr(IPrincipal(profile, None), 'id', None) == user.username

    user_ext = to_external_object(user)
    informal_username = user_ext.get('NonI18NFirstName', profile.realname) \
                     or user.username

    catalog_entry = ICourseCatalogEntry(course)

    course_start_date = ''

    if catalog_entry.StartDate:
        locale = IBrowserRequest(request).locale
        dates = locale.dates # pylint: disable=no-member
        formatter = dates.getFormatter('date', length='long')
        course_start_date = formatter.format(catalog_entry.StartDate)

    # pylint: disable=no-member
    html_sig = catalog_entry.InstructorsSignature.replace('\n', "<br />")

    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    course_end_date = catalog_entry.EndDate
    course_preview = catalog_entry.Preview
    course_archived = course_end_date and course_end_date < datetime.datetime.utcnow()

    for_credit_url = getattr(policy, 'FOR_CREDIT_URL', '')
    site_alias = getattr(policy, 'COM_ALIAS', '')
    brand_name = get_site_brand_name()

    args = {'profile': profile,
            'context': event,
            'user': user,
            'informal_username': informal_username,
            'course': catalog_entry,
            'support_email': support_email,
            'for_credit_url': for_credit_url,
            'site_alias': site_alias,
            'request': request,
            'brand': brand_name,
            'course_start_date': course_start_date,
            'instructors_html_signature': html_sig,
            'course_preview': course_preview,
            'course_archived': course_archived,
            'today': isodate.date_isoformat(datetime.datetime.now())}

    # Augment with our args providers
    providers = component.getUtilitiesFor(ICourseEnrollmentEmailArgsProvider)
    for unused_name, args_provider in list(providers):
        util_args = args_provider.get_email_args(user)
        if util_args:
            args.update(util_args)

    bcc = []
    providers = component.getUtilitiesFor(ICourseEnrollmentEmailBCCProvider)
    for unused_name, bcc_provider in list(providers):
        bcc_emails = bcc_provider.get_bcc_emails()
        if bcc_emails:
            bcc.extend(bcc_emails)

    package = getattr(policy, 'PACKAGE', 'nti.app.products.courseware')

    template = 'enrollment_confirmation_email'
    template = _get_template(catalog_entry, template, package)

    mailer = component.getUtility(ITemplatedMailer)
    mailer.queue_simple_html_text_email(
                template,
                subject=translate(_("Welcome to ${title}",
                                    mapping={'title': catalog_entry.Title})),
                recipients=[user],
                template_args=args,
                bcc=bcc,
                request=request,
                package=package,
                text_template_extension='.mak')
send_enrollment_confirmation = _send_enrollment_confirmation


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _enrollment_added(record, event):
    # We only want to do this when the user initiated the event,
    # not when it was done via automatic workflow.
    remote_user = get_remote_user()
    user = IUser(record, None)
    # Admins may enroll on behalf of students
    if queryInteraction() is None or remote_user != user:
        # no interaction, no email
        return

    # For now, the easiest way to detect that is to know that
    # automatic workflow is the only way to enroll in ES_CREDIT_DEGREE.
    # We also want a special email for 5-ME, so we avoid those as well.
    if record.Scope != ES_PUBLIC:
        return

    creator = event.object.Principal
    profile = IUserProfile(creator)
    email = getattr(profile, 'email', None)

    # Exactly one course at a time
    course = record.CourseInstance
    _send_enrollment_confirmation(event, creator, profile, email, course)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _join_communities_on_enrollment_added(record, unused_event):
    course = record.CourseInstance

    # get communities
    communities = set(get_enrollment_communities(course) or ())
    if not communities and ICourseSubInstance.providedBy(course):
        course = get_parent_course(course)
        communities = set(get_enrollment_communities(course) or ())
    if not communities:
        return

    # check for dup enrollment
    principal = IPrincipal(record.Principal, None)
    user = Entity.get_entity(principal.id) if principal else None
    if user is None:
        return

    for name in communities:
        community = Entity.get_entity(name)
        if community is None or not ICommunity.providedBy(community):
            logger.warning("Community %s does not exists", name)
            continue
        user.record_dynamic_membership(community)
        user.follow(community)


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _auto_enroll_on_enrollment_added(record, unused_event):
    course = record.CourseInstance
    main_entry = ICourseCatalogEntry(course, None)
    if main_entry is None:
        return

    # check for dup enrollment
    principal = IPrincipal(record.Principal, None)
    user = Entity.get_entity(principal.id) if principal else None
    if user is None:
        return

    # get parent course
    parent = get_parent_course(course)

    # get all catalog entries in the hierarchy
    main_entries = {
        ICourseCatalogEntry(x, None) for x in get_course_hierarchy(main_entry)
    }
    main_entries.discard(None)

    # Let's get the entries for the scope NTI/Enrollment/Scopes{scope}
    entries = set(get_enrollment_for_scope(course, record.Scope))
    if not entries and ICourseSubInstance.providedBy(course):  # look at parent
        entries = set(get_enrollment_for_scope(parent, record.Scope))
    if not entries:  # default to  NTI/Enrollment/Courses
        # get course entries
        entries = set(get_enrollment_courses(course))
        if not entries and ICourseSubInstance.providedBy(course):
            entries = set(get_enrollment_courses(parent))
    if not entries:
        return

    has_interaction = queryInteraction() is not None
    if has_interaction:
        endInteraction()
    try:
        for name in entries:
            entry = ICourseCatalogEntry(find_object_with_ntiid(name), None)
            if entry is None:
                logger.warning("Course entry %s does not exists", name)
                continue
            # make sure avoid circles
            if entry in main_entries:
                continue
            # check for deny open enrollment
            course = ICourseInstance(entry)
            if IDenyOpenEnrollment.providedBy(course) and record.Scope == ES_PUBLIC:
                continue
            # ready to enroll
            enrollments = ICourseEnrollments(course)
            # pylint: disable=too-many-function-args
            enrollment = enrollments.get_enrollment_for_principal(user)
            if enrollment is None:
                manager = ICourseEnrollmentManager(course)
                # pylint: disable=redundant-keyword-arg
                manager.enroll(user, scope=record.Scope)
    finally:
        if has_interaction:
            restoreInteraction()


@component.adapter(ICourseInstanceEnrollmentRecord, IObjectModifiedEvent)
def _auto_enroll_on_enrollment_modified(record, event):
    # A user may have open-enrolled and then purchase/switch enrollment
    _auto_enroll_on_enrollment_added(record, event)


def _update_enroll_last_modified(record):
    principal = IPrincipal(record.Principal, None)
    user = Entity.get_entity(principal.id) if principal else None
    if user is None or not IUser.providedBy(user):
        return
    # update enrollment
    timestamp = time.time()
    annotations = IAnnotations(user)
    annotations[USER_ENROLLMENT_LAST_MODIFIED_KEY] = timestamp
    # update last seen
    if queryInteraction() is not None:
        request = get_current_request()
        remote_user = get_remote_user(request)
        if remote_user == user:
            notify(UserLastSeenEvent(user, timestamp, request))


@component.adapter(ICourseInstanceEnrollmentRecord, IAfterIdAddedEvent)
def update_enrollment_modified_on_add(record, unused_event):
    _update_enroll_last_modified(record)


@component.adapter(ICourseInstanceEnrollmentRecord, IBeforeIdRemovedEvent)
def update_enrollment_modified_on_drop(record, unused_event):
    _update_enroll_last_modified(record)


@component.adapter(ICourseInstance, IBeforeTraverseEvent)
def course_traversal_context_subscriber(course, unused_event):
    """
    We commonly need access to the course context in underlying
    requests/decorators. Store that here for easy access.
    """
    request = get_current_request()
    if request is not None:
        request.course_traversal_context = course


@component.adapter(ICourseCatalogEntry, IBeforeTraverseEvent)
def catalog_entry_traversal_context_subscriber(entry, event):
    course_traversal_context_subscriber(ICourseInstance(entry), event)


@component.adapter(ICourseOutlineNode, IBeforeTraverseEvent)
def outline_node_traversal_context_subscriber(node, event):
    request = get_current_request()
    if getattr(request, 'course_traversal_context', None) is None:
        course = find_interface(node, ICourseInstance, strict=False)
        course_traversal_context_subscriber(course, event)


@component.adapter(ICourseContentPackageBundle, IContentBundleUpdatedEvent)
def _on_content_bundle_updated(bundle, event):
    course = find_interface(bundle, ICourseInstance, strict=False)
    added = event.added_packages
    removed = event.removed_packages
    notify(CourseBundleWillUpdateEvent(course, added, removed))


def _get_site_admin_all_sharing_scope_principal():
    site_name = getSite().__name__
    return '%s_%s' % (site_name, SITE_ADMIN_SHARING_SCOPES_PRINCIPAL_STR)


@component.adapter(IUser)
@interface.implementer(IGroupMember)
class SiteAdminSharingScopeGroups(object):
    """
    If the user is a site admin, we want to grant access to all sharing scopes.
    This should give the site admins access to any notes (UGD) shared to the
    course scopes. We do this by create returning a special principal id.
    """

    def __init__(self, context):
        self.groups = ()
        if is_site_admin(context):
            prin_str = _get_site_admin_all_sharing_scope_principal()
            self.groups = (IPrincipal(prin_str),)


@component.adapter(IShareableModeledContent)
@interface.implementer(ISupplementalACLProvider)
class CourseSharedScopeSupplmentalACLProvider(object):
    """
    If this context is shared with *any* :class:`ICourseInstanceSharingScope`,
    we add the site all course instance sharing scope principal to the ACL.

    Note, this approach will make sure the site admin has dynamic READ access
    to the UGD, but we currently are not doing anything to ensure this UGD
    is visible to site admins in any other context (search, etc).
    """

    def __init__(self, context):
        self.context = context

    @Lazy
    def __acl__(self):
        # We expect this list to be sparce and this lookup to be small.
        for sharing_target in self.context.sharingTargetNames or ():
            if is_valid_ntiid_string(sharing_target):
                shared_with_obj = find_object_with_ntiid(sharing_target)
                if ICourseInstanceSharingScope.providedBy(shared_with_obj):
                    # We found a scope; this must be a scope from a single course
                    # and a single site.
                    course = find_interface(shared_with_obj, ICourseInstance, strict=False)
                    if get_course_site_name(course) == getSite().__name__:
                        prin_str = _get_site_admin_all_sharing_scope_principal()
                        prin = IPrincipal(prin_str)
                        return acl_from_aces(ace_allowing(prin, ACT_READ, self))
        return None


@component.adapter(IHostPolicySiteManager, INewLocalSite)
def on_site_created(site_manager, unused_event):
    logger.info('Installed sharing scope utility (%s)',
                site_manager.__parent__.__name__)
    install_utility(CourseSharingScopeUtility(),
                    '++etc++CourseSharingScopeUtility',
                    ICourseSharingScopeUtility,
                    site_manager)


@component.adapter(ICourseInstance, IObjectCreatedEvent)
def _course_sharing_scopes_updated(course, unused_event=None):
    """
    When a new course is created, ensure all site admins are following
    all course scopes; this ensures they have access to shared notes.
    """
    sharing_scope_utility = component.queryUtility(ICourseSharingScopeUtility)
    if sharing_scope_utility is not None:
        site_admins = get_site_admins()
        for scope in course.SharingScopes.values():
            sharing_scope_utility.add_scope(scope)
            for site_admin in site_admins:
                site_admin.follow(scope)


@component.adapter(ICourseInstanceSharingScope, IBeforeIdRemovedEvent)
def on_course_scope_removed(scope, unused_event=None):
    """
    When a course scope is removed, remove site admins from following it.
    """
    sharing_scope_utility = component.queryUtility(ICourseSharingScopeUtility)
    if sharing_scope_utility is not None:
        sharing_scope_utility.remove_scope(scope)
    site_admins = get_site_admins()
    for site_admin in site_admins:
        site_admin.stop_following(scope)


@component.adapter(IUser, ISiteAdminAddedEvent)
def on_site_admin_added(site_admin, unused_event=None):
    """
    For new site admins, make sure they follow all course sharing scopes.
    """
    sharing_scope_utility = component.queryUtility(ICourseSharingScopeUtility)
    if sharing_scope_utility is not None:
        for scope in sharing_scope_utility.iter_scopes(parent_scopes=True):
            site_admin.follow(scope)


@component.adapter(IUser, ISiteAdminRemovedEvent)
def on_site_admin_removed(site_admin, unused_event=None):
    """
    For former site admins, make sure they no longer follow all course sharing
    scopes. This should only apply if they are *not* a member of the scope;
    they could be members as an instructor or enrolled user.
    """
    sharing_scope_utility = component.queryUtility(ICourseSharingScopeUtility)
    if sharing_scope_utility is not None:
        for scope in sharing_scope_utility.iter_scopes(parent_scopes=True):
            if site_admin not in scope:
                site_admin.stop_following(scope)

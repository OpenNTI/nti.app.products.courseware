#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Integrated courseware-related interfaces. This
is a high-level package built mostly upon the low-level
datastructures defined in :mod:`nti.app.products.courses`.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# disable missing self
# pylint:disable=I0011,E0213,E0211

from zope import schema
from zope import component
from zope import interface

from zope.container.constraints import contains

from zope.container.interfaces import IContainer

from zope.interface.common.mapping import IEnumerableMapping

from zope.location.interfaces import IContained

from zope.security.permission import Permission

from nti.appserver.interfaces import IContainerResource

from nti.appserver.workspaces.interfaces import IWorkspace
from nti.appserver.workspaces.interfaces import ICatalogCollection
from nti.appserver.workspaces.interfaces import IContainerCollection

from nti.base.interfaces import ILastModified

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance
from nti.contenttypes.courses.legacy_catalog import ILegacyCourseCatalogEntry

from nti.contenttypes.reports.interfaces import IReportContext

from nti.coremetadata.interfaces import IShouldHaveTraversablePath

from nti.externalization.interfaces import IIterable

from nti.ntiids.schema import ValidNTIID

from nti.schema.field import Bool
from nti.schema.field import Dict
from nti.schema.field import Object
from nti.schema.field import ValidURI
from nti.schema.field import ValidTextLine as TextLine

ACT_VIEW_ROSTER = Permission('nti.actions.courseware.view_roster')
ACT_VIEW_ACTIVITY = Permission('nti.actions.courseware.view_activity')


class ICourseCatalogLegacyContentEntry(ILegacyCourseCatalogEntry):
    """
    Marker interface for a legacy course catalog entry
    """
    ContentPackageNTIID = ValidNTIID(title=u"The NTIID of the root content package",
									 required=False)


class ILegacyCommunityBasedCourseInstance(ILegacyCourseInstance):
    """
    Marker interface for a legacy course instance
    """

    LegacyScopes = Dict(title=u"'public' and 'restricted' entity ids",
                        readonly=True)

    ContentPackageBundle = interface.Attribute(
        "A mock bundle, having a ContentPackages iterable")


class ICourseInstanceActivity(IContained, ILastModified):
    """
    A firehose implementation of activity relating
    to a course and typically expected to be visible to
    instructors/administrators of the course.

    An implementation of this interface will be available
    by adapting a course to it.
    """

    def __len__():
        "How many items are in this collection."

    def append(activity):
        """
        Note that the ``activity`` relevant to this course
        has happened. The ``activity`` object must have an intid,
        and it will be stored along with an approximate timestamp
        of when it occurred. Note that if activity is happening on multiple
        machines, relative times will only be as good as clock
        synchronization.
        """

    def remove(activity):
        """
        Remove the activity from the list for this course.
        Note that this may be very expensive.
        """

    def items(min=None, max=None, excludemin=False, excludemax=False):
        """
        Return an iterator over the activity items stored for this
        course. The iterator is returned in sorted order, with
        most recent items first.

        :keyword min: If given, a timestamp.
        :keyword max: If given, a timestamp.
        """


class ICoursesWorkspace(IWorkspace):
    """
    A workspace containing data for courses.
    """


class ICoursePagesContainerResource(IContainerResource):
    """
    A pages resource on a course.
    """
    course = Object(ICourseInstance,
                    title=u"The course that owns the page container")

    ntiid = schema.TextLine(title=u"The NTIID of the container")


class ICourseCollection(IContainerCollection):
    """
    A course collection.
    """


class ICoursesCollection(IContainerCollection):
    """
    A collection of courses.
    """


class IEnrolledCoursesCollection(ICoursesCollection):
    """
    A collection (local to a user) of courses he is enrolled in
    (:class:`.ICourseInstanceEnrollment`)
    """


class IAllCoursesCollection(ICoursesCollection):
    """
    A collection of all courses in a site.
    """


class ICourseInstanceEnrollment(IShouldHaveTraversablePath,
                                IReportContext):
    """
    An object representing a principal's enrollment in a course
    instance.

    Implementations should be adaptable to their course instance
    and the corresponding catalog entry.

    These objects should be non-persistent and derived from the
    underlying :class:`.ICourseInstanceEnrollmentRecord`, but
    independently mutable.
    """

    __name__ = interface.Attribute("The name of the enrollment is the same as the CourseInstance.")

    CourseInstance = Object(ICourseInstance)
    CourseInstance.setTaggedValue('_ext_excluded_out', True)

    Username = TextLine(title=u"The user this is about",
                        required=False,
                        readonly=True)


class ILegacyCourseInstanceEnrollment(ICourseInstanceEnrollment):
    """
    An object with information about enrollment in a legacy course.
    """

    LegacyEnrollmentStatus = TextLine(title=u"The type of enrollment, ForCredit or Open",
                                      required=True,
                                      readonly=True,
                                      default=u'Open')

    RealEnrollmentStatus = TextLine(title=u"The type of enrollment (Scope)",
                                    required=False,
                                    readonly=True)


class IPrincipalEnrollmentCatalog(IPrincipalEnrollments):
    """
    Extends the base enrollments interface to be in terms
    of the :class:`.ICourseInstanceEnrollment` objects defined
    in this module.

    There can be multiple catalogs of enrollments for courses
    that are managed in different ways. Therefore, commonly
    implementations will be registered as subscription adapters
    from the user.
    """

    def iter_enrollments():
        """
        Iterate across :class:`.ICourseInstanceEnrollment` objects, or at
        least something that can be adapted to that interface.
        (Commonly, this will return actual :class:`.ICourseInstance`
        objects; we provide an adapter from that to the enrollment.)
        """


class IAdministeredCoursesCollection(ICoursesCollection):
    """
    A collection (local to a user) of courses he administers
    (:class:`nti.contenttypes.courses.interfaces.ICourseInstanceAdministrativeRole`)
    """


class IAdministeredCoursesFavoriteFilter(interface.Interface):

    def include_entry(user, entry):
        """
        For the administered courses favorites collection,
        allow utilities to be defined to restrict which
        entries are returned.
        """


from nti.contentlibrary.interfaces import ILegacyCourseConflatedContentPackage


class ILegacyCourseConflatedContentPackageUsedAsCourse(ILegacyCourseConflatedContentPackage):
    """
    A marker applied on top of a content package that was already
    conflated when it is actually being used by a course.

    Remember that this can only happen in the global library with non-persistent
    content packages; the code in :mod:`legacy_catalog` will refuse to turn
    any persistent content package in a site library into a course. Therefore this
    marker interface can be used to distinguish things that are actually being
    used as :class:`ILegacyCommunityBasedCourseInstance` and which are not.

    When this marker is applied, instances should get access to
    an attribute ``_v_global_legacy_catalog_entry`` that points to the catalog
    entry, which should also be global and not persistent. Access this attribute
    to get the catalog entry; yes, it will lead to warnings in your code about
    a private attribute, but it will be easy to clean them up later, and we want
    this ugliness to stand out.
    """

# A preliminary special type of NTIID that refers to an abstract
# notion of a topic within a particular abstract course. When
# resolved, we will find the specific course (sub)instance the user is
# enrolled in and return the closest matching topic. This type of
# NTIID is semi-suitable for use in content and other long-lived places.
#
# The `provider` field should be the value of the `ProviderUniqueID`
# from the course catalog for the top-level course (not section/subinstance).
NTIID_TYPE_COURSE_SECTION_TOPIC = 'Topic:EnrolledCourseSection'

# Similar to :const:`.NTIID_TYPE_COURSE_SECTION_TOPIC`, but instead
# returns the top-level course topic, never the course topic
# for a subsection.
NTIID_TYPE_COURSE_TOPIC = 'Topic:EnrolledCourseRoot'

# NTIIDs that look up named forums in courses.
NTIID_TYPE_COURSE_SECTION_FORUM = 'Forum:EnrolledCourseSection'

NTIID_TYPE_COURSE_FORUM = 'Forum:EnrolledCourseRoot'


class IEnrollmentOption(IContained):
    """
    Marker interface for a course/entry enrollment option
    """

    Name = TextLine(title=u"Enrollment option name", required=True)
    Name.setTaggedValue('_ext_excluded_out', True)

    CatalogEntryNTIID = TextLine(title=u"Catalog entry NTIID", required=False)
    CatalogEntryNTIID.setTaggedValue('_ext_excluded_out', True)

    title = TextLine(title=u"Title",
                     required=False)

    description = TextLine(title=u"Description",
                           required=False)

    drop_title = TextLine(title=u"Drop title",
                          required=False)

    drop_description = TextLine(title=u"Drop description",
                                required=False)


class IExternalEnrollmentOption(IEnrollmentOption):
    """
    An :class:`IEnrollmentOption` that may point the user to an external URL
    for enrollment into the course.
    """

    enrollment_url = ValidURI(title=u"Enrollment URL",
                              required=True)

    drop_url = ValidURI(title=u"Drop URL",
                        required=False)


class IEnrollmentOptionContainer(IContainer):
    """
    Container for persistent :class:`IEnrollmentOption` objects.
    """

    contains(IEnrollmentOption)


class IOpenEnrollmentOption(IEnrollmentOption):
    """
    Open course/entry enrollment option
    """

    Enabled = Bool(title=u"If the course allows open enrollment",
                   required=False,
                   default=True)


class IEnrollmentOptions(IEnumerableMapping):
    """
    Marker interface for an object that hold :class:`.IEnrollmentOption` objects
    for a course.
    """

    def append(option):
        """
        add an enrollment option
        """


class IEnrollmentOptionProvider(interface.Interface):
    """
    subscriber for a course/entry enrollment options
    """

    def iter_options():
        """
        return an iterable of :class:`.IEnrollmentOption` for the specified
        course
        """


class IAvailableEnrollmentOptionProvider(interface.Interface):
    """
    Returns available :class:`IEnrollmentOption` objects that could be set on
    a course.
    """

    def iter_options():
        """
        return an iterable of :class:`.IEnrollmentOption` available
        """


class IRanker(interface.Interface):
    """
    Knows how to rank a disparate set of items.
    """

    def rank(items):
        """
        Returns the modified set of items, ranked according to an underlying algorithm.
        """


class IViewStats(interface.Interface):
    """
    Gives view stats on the adapted object.
    """


class IUsageStats(interface.Interface):

    def get_stats(self, scope=None):
        """
        Return stats for course users, optionally by scope.
        """

    def get_top_stats(self, scope=None, top_count=None):
        """
        Return top usage stats for course users, optionally by scope.
        """


class IVideoUsageStats(IUsageStats):
    """
    Returns video usage stats for a course.
    """

class IResourceUsageStats(IUsageStats):
    """
    Returns resource usage stats for a course.
    """

class IUserUsageStats(interface.Interface):

    def get_stats(self):
        """
        Return stats for course users, optionally by scope.
        """

class IUserVideoUsageStats(IUserUsageStats):
    """
    Returns video usage stats for a course and user.
    """

class IUserResourceUsageStats(IUserUsageStats):
    """
    Returns resource usage stats for a course and user.
    """

# Suggested contacts


from nti.dataserver.users.interfaces import ISuggestedContactsProvider


class IClassmatesSuggestedContactsProvider(ISuggestedContactsProvider):

    def suggestions_by_course(user, course):
        """
        return classmates/contacts suggestions by course
        """


# Email options


class ICourseEnrollmentEmailBCCProvider(interface.Interface):

    def get_bcc_emails(user):
        """
        Return BCC email addresses.
        """


class ICourseEnrollmentEmailArgsProvider(interface.Interface):

    def get_email_args(user):
        """
        Return email args for the given user.
        """


# publishable vendor info


class ICoursePublishableVendorInfo(interface.Interface):
    """
    marker interface for a vendor info that can be made public.
    this will be registered as subscribers
    """

    def info():
        """
        return a map with public info
        """


def get_course_publishable_vendor_info(context):
    result = dict()
    course = ICourseInstance(context, None)
    subscribers = component.subscribers((course,),
                                        ICoursePublishableVendorInfo)
    for s in list(subscribers):
        info = s.info()
        result.update(info or {})
    return result


class ICoursesCatalogCollection(ICatalogCollection):
    """
    The :class:``ICatalogCollection`` that contains course catalog entries.
    """


class IAvailableCoursesProvider(interface.Interface):
    """
    An adapter to fetch available courses for a user.
    """

    def get_available_entries(self):
        """
        Return a sequence of :class:`ICourseCatalogEntry` objects the user is
        not enrolled in and that are available to be enrolled in.
        """


class IAllCoursesCollectionAcceptsProvider(IIterable):
    """
    A subscriber which provides an `Iterable` of MIME types to use as elements
    in an `IAllCoursesCollection.accepts` `Iterable`.
    """


class ICourseTabConfigurationUtility(interface.Interface):
    """
    A utility that should be registered in site where it allows
    permitted users access to the course tab configuration.
    """
    def can_edit_tabs(user, course):
        """
        Return True if the given user has access to the course tab configuration.
        """


class ICourseSharingScopeUtility(interface.Interface):
    """
    A utility that enables quick lookup of all sharing scopes
    contained within a site.
    """

    def iter_scopes(scope_name=None, parent_scopes=True):
        """
        Iterate over the sharing scopes within this utility, optionally
        filtering by scope name.
        If `parent_scopes` is False, we do not query the parent site
        utility.
        """

    def iter_ntiids(parent_ntiids=True):
        """
        Iterate over the scope NTIIDs.
        """

    def add_scope(scope):
        """
        Add a scope to the utility.
        """

    def remove_scope(scope):
        """
        Remove a scope from the utility.
        """

# deprecations


import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "Moved to nti.app.products.courseware.invitation.interfaces",
    "nti.app.products.courseware.invitation.interfaces",
    "ICourseInvitation")


zope.deferredimport.deprecatedFrom(
    "Moved to nti.app.products.courseware.resources.interfaces",
    "nti.app.products.courseware.resources.interfaces",
    "ICourseRootFolder",
    "ICourseContentFile",
    "ICourseContentFolder")

zope.deferredimport.deprecatedFrom(
    "Moved to nti.contenttypes.courses",
    "nti.contenttypes.courses.interfaces",
    "ICourseCatalogEntry",
    "IUserAdministeredCourses",
    "ICourseCatalogInstructorInfo",
    "ICourseInstanceAvailableEvent",
    "CourseInstanceAvailableEventg",
    "ICourseInstanceAdministrativeRole",
    'IPrincipalAdministrativeRoleCatalog')

zope.deferredimport.deprecatedFrom(
    "Moved to nti.contenttypes.courses",
    "nti.contenttypes.courses.legacy_catalog",
    "ICourseCatalogInstructorLegacyInfo",
    "ICourseCreditLegacyInfo",
    'ICourseCatalogLegacyEntry')

zope.deferredimport.deprecated(
    "Moved to nti.contenttypes.courses",
    # XXX: Note the aliasing: This is somewhat dangerous if we
    # attempt to register things by this interface!
    ICourseCatalog="nti.contenttypes.courses.interfaces:IWritableCourseCatalog")

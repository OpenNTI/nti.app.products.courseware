#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import namedtuple

from numbers import Number

import BTrees

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from pyramid.threadlocal import get_current_request

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.intid.interfaces import IIntIds

from zope.traversing.interfaces import IPathAdapter

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware import VIEW_LESSON_COMPLETION_STATS

from nti.app.products.courseware.interfaces import ACT_VIEW_ROSTER
from nti.app.products.courseware.interfaces import ACT_VIEW_ACTIVITY

from nti.app.products.courseware.interfaces import ICourseCollection
from nti.app.products.courseware.interfaces import ICourseInstanceActivity
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICoursePagesContainerResource

from nti.app.products.courseware.utils import get_enrollment_options

from nti.app.products.courseware.views import MessageFactory as _

from nti.app.products.courseware.views import VIEW_CONTENTS
from nti.app.products.courseware.views import VIEW_COURSE_ACTIVITY
from nti.app.products.courseware.views import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware.views import VIEW_COURSE_ENROLLMENT_ROSTER
from nti.app.products.courseware.views import VIEW_COURSE_TAB_PREFERENCES

from nti.app.renderers.caching import AbstractReliableLastModifiedCacheController

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.interfaces import IIntIdUserSearchPolicy

from nti.appserver.pyramid_authorization import has_permission

from nti.appserver.relevant_ugd_views import _RelevantUGDView

from nti.appserver.ugd_edit_views import ContainerContextUGDPostView
from nti.appserver.ugd_edit_views import UGDPutView

from nti.appserver.ugd_query_views import Operator
from nti.appserver.ugd_query_views import _combine_predicate

from nti.assessment.interfaces import IQAssignment

from nti.common.string import is_true

from nti.contenttypes.completion.interfaces import ICompletableItem
from nti.contenttypes.completion.interfaces import ICompletedItemProvider
from nti.contenttypes.completion.interfaces import ICompletableItemProvider
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.completion.utils import is_item_required

from nti.contenttypes.courses.administered import get_course_admin_role

from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseTabPreferences
from nti.contenttypes.courses.interfaces import ICourseOutlineContentNode
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.coremetadata.interfaces import IContextLastSeenContainer

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_site_admin
from nti.dataserver.authorization import is_admin_or_content_admin

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import ILocatedExternalSequence

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import decorate_external_mapping

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.oids import to_external_ntiid_oid as toExternalOID

from nti.property.property import alias

from nti.publishing.interfaces import IPublishable
from nti.publishing.interfaces import ICalendarPublishable

from nti.zodb.containers import bit64_int_to_time
from nti.zodb.containers import time_to_64bit_int

OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT
LAST_MODIFIED = StandardExternalFields.LAST_MODIFIED

union_operator = Operator.union

logger = __import__('logging').getLogger(__name__)


class OutlineContentsCacheController(AbstractReliableLastModifiedCacheController):
    """
    The outline contents cache is controlled by an eTag comprising of the set
    of node ntiids as well as the outline last modified time. The outline node
    last modified time is sufficient since children last modified times
    percolate up to the course outline object itself.
    """

    max_age = 0

    def __init__(self, context, request=None, visible_ntiids=()):
        super(OutlineContentsCacheController, self).__init__(context, request)
        self.visible_ntiids = visible_ntiids or ()

    @property
    def _context_specific(self):
        return sorted(x for x in self.visible_ntiids)

#: A simple structure to hold node content data.
OutlineNodeContents = namedtuple("OutlineNodeContents",
                                 ("node", "contents",
                                  "lesson_ntiid",
                                  "node_is_published",
                                  "lesson_is_published"))


@view_config(route_name='objects.generic.traversal',
             context=ICourseOutline,
             request_method='GET',
             permission=nauth.ACT_READ,
             renderer='rest',
             name=VIEW_CONTENTS)
class CourseOutlineContentsView(AbstractAuthenticatedView):
    """
    The view to get the actual contents of a course outline.  By default
    this view returns all nodes the requesting user has access to.  For
    admins, instructors, and editors this may include nodes that are not
    visible to other types of users.  To return contents as if a non editor
    requested them a query param of `omit_unpublished=True` can be provided.
    This param has no effect if the requesting user is not a content editor.

    We flatten all the children directly into the returned nodes at
    this level because the default externalization does not.
    """

    @Lazy
    def _is_course_editor(self):
        # Course/outline editors should have access to edit all nodes
        return has_permission(nauth.ACT_CONTENT_EDIT,
                              self.context,
                              self.request)

    @Lazy
    def show_unpublished(self):
        """
        Show unpublished nodes, defaults to True.
        """
        omit_unpublished = False
        try:
            value = self.request.params.get('omit_unpublished', False)
            omit_unpublished = is_true(value)
        except ValueError:
            pass
        return not omit_unpublished and self._is_course_editor

    def _is_published(self, item):
        """
        Node is published.
        """
        return not IPublishable.providedBy(item) \
            or item.is_published(principal=self.remoteUser,
                                 context=self.context)

    def _get_node_lesson(self, node):
        return INTILessonOverview(node, None)

    def _is_content_available(self, item):
        """
        Lesson is available if published or if we're an editor.
        """
        lesson = self._get_node_lesson(item)
        # Returns True if lesson is None (implying outline node)
        result = self._is_published(lesson)
        return result

    @Lazy
    def _visible_nodes(self):
        """
        Builds a tree of `OutlineNodeContents` objects to be externalized.
        """
        result = []
        def _recur(the_list, the_nodes):
            for node in the_nodes:
                node_is_published = self._is_published(node)
                if not node_is_published and not self.show_unpublished:
                    continue
                contents = None
                lesson_ntiid = None
                lesson_is_published = self._is_content_available(node)
                if lesson_is_published or self.show_unpublished:
                    contents = _recur([], node.values())
                    lesson_ntiid = node.LessonOverviewNTIID
                node_contents = OutlineNodeContents(node, contents,
                                                    lesson_ntiid,
                                                    node_is_published,
                                                    lesson_is_published)
                the_list.append(node_contents)
            return the_list
        _recur(result, self.context.values())
        return result

    @Lazy
    def _externalized_nodes(self):
        """
        Externalize our node tree appropriately based on visible underlying
        contents.
        """
        result = []
        def _recur(the_list, the_nodes):
            for outline_node in the_nodes:
                ext_node = to_external_object(outline_node.node)
                if outline_node.contents is not None:
                    ext_node['contents'] = _recur([], outline_node.contents)
                else:
                    # Some clients drive behavior based on this attr.
                    ext_node.pop('ContentNTIID', None)
                # Pretty pointless to send these
                ext_node.pop(OID, None)
                the_list.append(ext_node)
            return the_list
        _recur(result, self._visible_nodes)
        return result

    @Lazy
    def _published_ntiids(self):
        """
        All published ntiids of our node structure.The set of published ntiids
        will be a subset of the set of visible nodes.
        """
        result = []
        def _recur(accum, outline_node):
            # Gather our node and lesson ntiids, and then underlying contents
            # (recursively) if available.
            if outline_node.node_is_published:
                node_ntiid = getattr(outline_node.node, 'ntiid', '')
                if node_ntiid:
                    accum.append(node_ntiid)
            if outline_node.lesson_is_published:
                accum.append(outline_node.lesson_ntiid)
            for child_outline_node in outline_node.contents or ():
                _recur(accum, child_outline_node)
        # pylint: disable=not-an-iterable
        for outline_node in self._visible_nodes:
            _recur(result, outline_node)
        return result

    def caching(self):
        # Since we externalize ourselves, attempt to return early if we can.
        # This call can be expensive to externalize now that we have massive
        # course outlines in the wild. The etag is based on the set of ntiids
        # of nodes and lessons that are published.
        cache_controller = OutlineContentsCacheController(self.context,
                                                          visible_ntiids=self._published_ntiids)
        cache_controller(self.context, {'request': self.request})

    def externalize_node_contents(self, node):
        self.context = node
        result = ILocatedExternalSequence(self._externalized_nodes)
        result.__name__ = self.request.view_name
        result.__parent__ = self.context
        return result

    def __call__(self):
        self.caching()
        return self.externalize_node_contents(self.context)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
class CourseEnrollmentRosterPathAdapter(Contained):
    """
    We use a path adapter for the enrollment object so that we
    can traverse to actual course enrollment objects for enrolled users,
    thus letting us have named views or further traversing
    for those objects.
    """

    def __init__(self, course, unused_request=None):
        self.__parent__ = course
        self.__name__ = VIEW_COURSE_ENROLLMENT_ROSTER

    course = alias('__parent__')

    def __getitem__(self, username):
        username = username.lower()
        # We can do better than this interface now
        # pylint: disable=too-many-function-args
        enrollments_iter = ICourseEnrollments(self.__parent__).iter_enrollments()
        for record in enrollments_iter:
            user = IUser(record)
            # pylint: disable=no-member
            if user.username.lower() == username:
                enrollment = component.getMultiAdapter((self.__parent__, record),
                                                       ICourseInstanceEnrollment)
                enrollment.CourseInstance = None
                return enrollment
        # not found
        raise KeyError(username)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=CourseEnrollmentRosterPathAdapter,
             permission=ACT_VIEW_ROSTER)
class CourseEnrollmentRosterGetView(AbstractAuthenticatedView,
                                    BatchingUtilsMixin):
    """
    Support retrieving the enrollment status of members of the class.
    Any extra path is taken as the username to lookup and only that
    user's record is returned (or a 404 if the user is not found
    enrolled); query parameters are ignored.

    The return dictionary will have the following entries:

    Items
            A list of enrollment objects.

    FilteredTotalItemCount
            The total number of items that match the filter, if specified;
            identical to TotalItemCount if there is no filter.

    TotalItemCount
            How many total enrollments there are. If any filter, sorting
            or paging options are specified, this will be the same as the
            number of enrolled students in the class (because we will
            ultimately return that many rows due to the presence of null
            rows for non-submitted students).

    The following query parameters are supported:

    sortOn
            The field to sort on. Options are ``realname`` to sort on the parts
            of the user's realname (\"lastname\" first; note that this is
            imprecise and likely to sort non-English names incorrectly.);
            username;lastSeenTime (course last seen time)``.

    sortOrder
            The sort direction. Options are ``ascending`` and
            ``descending``. If you do not specify, a value that makes the
            most sense for the ``sortOn`` parameter will be used by
            default.

    filter
            Whether to filter the returned data in some fashion. Several
            values are defined:

            * ``LegacyEnrollmentStatusForCredit``: Only students that are
              enrolled for credit are returned. An entry in the dictionary is
              returned for each such student, even if they haven't submitted;
              the value for students that haven't submitted is null.

            * ``LegacyEnrollmentStatusOpen``: Only students that are
              enrolled NOT for credit are returned. An entry in the dictionary is
              returned for each such student, even if they haven't submitted;
              the value for students that haven't submitted is null.

    usernameSearchTerm
            If provided, only users that match this search term
            will be returned. This search is based on the username and
            realname and alias, and does prefix matching, the same as
            the normal search algorithm for users. This is independent
            of filtering.

    batchSize
            Integer giving the page size. Must be greater than zero.
            Paging only happens when this is supplied together with
            ``batchStart`` (or ``batchAround`` for those views that support it).

    batchStart
            Integer giving the index of the first object to return,
            starting with zero. Paging only happens when this is
            supplied together with ``batchSize``.

    """

    @classmethod
    def user_record(cls, record):
        try:
            return IUser(record, None)
        except TypeError:
            return None

    def _externalize(self, record):
        """
        NOTE: Rendering the same CourseInstance over and over is hugely
        expensive, and massively bloats the response...77 students
        can generate 12MB of response. So we don't include the course
        instance.

        Because we are now typically waking up the user profile from the
        database *anyway* when we request enrollment rosters (to sort on),
        it's relatively cheap and useful to the (current) UI to send back
        the user details.
        """
        record = ICourseInstanceEnrollment(record)
        record.CourseInstance = None
        external = to_external_object(record)

        user = self.user_record(record)
        if user is not None:
            ext_profile = to_external_object(user, name='summary')
            external['UserProfile'] = ext_profile
        return external

    def _build_scope_filter(self, filter_name):
        filter_status = None
        if filter_name:
            if filter_name in ENROLLMENT_SCOPE_MAP:
                filter_status = filter_name
            else:
                raise hexc.HTTPBadRequest("Unsupported filteroption")

        if filter_status:
            def _filter(x):
                x = ICourseInstanceEnrollment(x)
                return x.RealEnrollmentStatus == filter_status
            return _filter
        return lambda x: x

    def _build_user_filter(self, username_search_term):
        if username_search_term:
            policy = component.getAdapter(self.remoteUser,
                                          IIntIdUserSearchPolicy,
                                          name='comprehensive')
            id_util = component.getUtility(IIntIds)
            matched_ids = policy.query_intids(username_search_term.lower())
            def _filter(x):
                uid = id_util.queryId(IUser(x, None))
                return uid is not None and uid in matched_ids
            return _filter
        return lambda unused_x: True

    def _record_filter(self, filter_name, username_search_term):
        scope = self._build_scope_filter(filter_name)
        user = self._build_user_filter(username_search_term)
        return lambda x: scope(x) and user(x)

    def __call__(self):
        request = self.request
        context = request.context.course
        course = context
        course_ntiid = context.ntiid

        result = LocatedExternalDict()
        result.__name__ = request.view_name
        result.__parent__ = course

        enrollments = ICourseEnrollments(course)
        # pylint: disable=too-many-function-args
        enrollments_iter = enrollments.iter_enrollments()

        filter_name = self.request.params.get('filter')
        sort_name = self.request.params.get('sortOn', '').lower()
        sort_reverse = self.request.params.get('sortOrder', 'ascending')
        sort_reverse = sort_reverse == 'descending'
        username_search_term = self.request.params.get('usernameSearchTerm')

        if sort_name == 'realname':
            # An alternative way to do this would be to get the
            # intids of the users (available from the EntityContainer)
            # and then have an index on the reverse name in the entity
            # catalog (we have the name parts, but keyword indexes are
            # not sortable)
            def _key(record):
                parts = None
                user = self.user_record(record)
                named = IFriendlyNamed(user, None)
                if named is not None:
                    parts = named.get_searchable_realname_parts()
                parts = reversed(parts) if parts else parts # last name first
                return ' '.join(parts).lower() if parts else ''

            enrollments_iter = sorted(enrollments_iter,
                                      key=_key,
                                      reverse=sort_reverse)
        elif sort_name == 'username':
            def _key(x):
                user = self.user_record(x)
                return getattr(user, 'username', '')
            enrollments_iter = sorted(enrollments_iter,
                                      key=_key,
                                      reverse=sort_reverse)

        elif sort_name == 'lastseentime':
            def _key(x):
                result = None
                user = self.user_record(x)
                container = IContextLastSeenContainer(user, None)
                if container:
                    result = container.get_timestamp(course_ntiid)
                return result or 0
            enrollments_iter = sorted(enrollments_iter,
                                      key=_key,
                                      reverse=sort_reverse)
        elif sort_name:  # pragma: no cover
            # We're not silently ignoring because in the past
            # we've had clients send in the wrong value for a long time
            # before anybody noticed
            raise hexc.HTTPBadRequest("Unsupported sort option")

        result['TotalItemCount'] = enrollments.count_enrollments()

        # We could theoretically be more efficient with the user of
        # the IEnumerableEntity container and the scopes, especially
        # if we did that FIRST, before getting the enrollments, and
        # paging that range of usernames, and doing the entity
        # username search on the intid set it returns. However, this
        # is good enough for now. Sorting is maintained from above.
        # Note that it will blow up once we have non-legacy courses.

        if filter_name or username_search_term: #avoid reifying the list again if we don't have to
            record_filter = self._record_filter(filter_name, username_search_term)
            enrollments_iter = [x for x in enrollments_iter if record_filter(x)]
            result['FilteredTotalItemCount'] = len(enrollments_iter)

        self._batch_items_iterable(result, enrollments_iter)

        # Notice we don't use `_batch_items_iterable`'s selector to perform the
        # externalization. That selector gets called on every item from the beginnning
        # of the iterable up to batchStart + batchSize.  That's a lot of unnecessary
        # and expensive externalization.
        result[ITEMS] = [self._externalize(x) for x in result[ITEMS]]
        result[ITEM_COUNT] = len(result[ITEMS])
        # We have no last modified for this
        return result

@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=CourseEnrollmentRosterPathAdapter,
             permission=ACT_VIEW_ROSTER,
             name='summary')
class CourseRosterSummary(AbstractAuthenticatedView):

    def __call__(self):
        # pylint: disable=no-member
        course = self.context.course
        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = course

        # pylint: disable=too-many-function-args
        enrollments = ICourseEnrollments(course)
        result['TotalEnrollments'] = enrollments.count_enrollments()

        counts = {}
        for scope in ENROLLMENT_SCOPE_MAP:
            counts[scope] = enrollments.count_scope_enrollments(scope)

        result['TotalEnrollmentsByScope'] = counts

        # Legacy, non-interface methods
        try:
            result['TotalLegacyOpenEnrolledCount'] = enrollments.count_legacy_open_enrollments()
            result['TotalLegacyForCreditEnrolledCount'] = enrollments.count_legacy_forcredit_enrollments()
        except AttributeError:
            pass

        return result


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def CourseActivityPathAdapter(context, unused_request=None):
    return ICourseInstanceActivity(context)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseCatalogEntry, IRequest)
def CatalogEntryActivityPathAdapter(context, unused_request=None):
    course = ICourseInstance(context)
    return ICourseInstanceActivity(course)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=ICourseInstanceActivity,
             permission=ACT_VIEW_ACTIVITY)
class CourseActivityGetView(AbstractAuthenticatedView,
                            BatchingUtilsMixin):

    def __call__(self):
        request = self.request
        context = request.context
        course = context

        activity = ICourseInstanceActivity(course)

        result = LocatedExternalDict()
        result.__parent__ = course
        result.__name__ = VIEW_COURSE_ACTIVITY
        result['TotalItemCount'] = total_item_count = len(activity)

        # NOTE: We could be more efficient by paging around
        # the timestamp rather than a size
        batch_size, batch_start = self._get_batch_size_start()

        number_items_needed = total_item_count
        if batch_size is not None and batch_start is not None:
            number_items_needed = min(batch_size + batch_start + 2,
                                      total_item_count)

        self._batch_tuple_iterable(result, activity.items(),
                                   number_items_needed,
                                   batch_size, batch_start)

        decorate_external_mapping(activity, result)

        last_modified = max(activity.lastModified, result['lastViewed'])
        result.lastModified = last_modified
        result[LAST_MODIFIED] = last_modified
        return result


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='PUT',
             context=ICourseInstanceActivity,
             permission=ACT_VIEW_ACTIVITY,
             name='lastViewed')
class CourseActivityLastViewedDecorator(AbstractAuthenticatedView,
                                        ModeledContentUploadRequestUtilsMixin):
    """
    Because multiple administrators might have access to the course
    activity, we maintain a per-user lastViewed timestamp as an
    annotation on the activity object.

    The annotation itself is a :class:`BTrees.OLBTree`, with usernames as
    keys and the values being int-encoded time values.

    This object is both a view callable for updating that value,
    and a decorator for putting that value in the object.
    """

    inputClass = Number

    KEY = 'nti.app.products.courseware.decorators._CourseInstanceActivityLastViewedDecorator'

    def __init__(self, request=None):
        if IRequest.providedBy(request):  # as a view
            super(CourseActivityLastViewedDecorator, self).__init__(request)
        # otherwise, we're a decorator and no args are passed

    def decorateExternalMapping(self, context, result):
        request = get_current_request()
        if request is None or not request.authenticated_userid:
            return

        if not has_permission(ACT_VIEW_ACTIVITY, context, request):
            return False

        username = request.authenticated_userid

        annot = IAnnotations(context)
        mapping = annot.get(self.KEY)
        if mapping is None or username not in mapping:
            result['lastViewed'] = 0
        else:
            result['lastViewed'] = bit64_int_to_time(mapping[username])

        # And tell them where to PUT it :)
        links = result.setdefault(LINKS, [])
        links.append(Link(context,
                          rel='lastViewed',
                          elements=('lastViewed',),
                          method='PUT'))

    def __call__(self):
        context = self.request.context
        username = self.request.authenticated_userid
        annot = IAnnotations(context)
        mapping = annot.get(self.KEY)
        if mapping is None:
            mapping = BTrees.OLBTree.BTree()
            annot[self.KEY] = mapping
        now = self.readInput()
        mapping[username] = time_to_64bit_int(now)
        return now


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='POST',
             context=ICourseInstance,
             permission=nauth.ACT_READ,
             name='Pages')
class CoursePagesView(ContainerContextUGDPostView):
    """
    A pages view on the course.  We subclass ``ContainerContextUGDPostView`` in
    order to intervene and annotate our ``IContainerContext``
    object with the course context.

    Reading/Editing/Deleting will remain the same.
    """


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             request_method='GET',
             context=ICoursePagesContainerResource,
             permission=nauth.ACT_READ,
             name='RelevantUGD')
class RelevantUGDGetView(_RelevantUGDView):
    """
    A pages view on the course to get relevant UGD content.
    Relevant UGD is defined as the set of objects which are top-level,
    shared with the user, and either have no context_id or have
    a context_id matching the course context from the request.
    """

    def __init__(self, request, unused_user=None, unused_ntiid=None):
        # pylint: disable=no-member
        self.request = request
        _RelevantUGDView.__init__(self, request, self.remoteUser, self.context.ntiid)

    def _make_complete_predicate(self, operator=union_operator):
        predicate = _RelevantUGDView._make_complete_predicate(self, operator)
        course_instance = ICourseInstance(self.request, None)
        allowed_id = toExternalOID(course_instance)

        def _filter(obj):
            if obj.context_id and obj.context_id == allowed_id:
                return True
            return False

        predicate = _combine_predicate(_filter,
                                       predicate,
                                       operator=Operator.intersection)
        return predicate


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name="EnrollmentOptions",
               permission=ACT_VIEW_ROSTER)
class CourseEnrollmentOptionsGetView(AbstractAuthenticatedView):

    def __call__(self):
        options = get_enrollment_options(self.context)
        return options


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_USER_COURSE_ACCESS,
               request_method='GET',
               permission=nauth.ACT_READ)
class UserCoursePreferredAccessView(AbstractAuthenticatedView):
    """
    A view that returns the preferred user access to the course context. This
    may be an administrative role or an enrollment record. We should mimic what
    is returned by the course workspaces.
    """

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    @Lazy
    def _is_admin(self):
        return is_admin_or_content_admin(self.remoteUser) \
            or is_course_instructor_or_editor(self._course, self.remoteUser) \
            or has_permission(nauth.ACT_CONTENT_EDIT, self.context, self.request)

    def __call__(self):
        result = None
        if self._is_admin:
            result = get_course_admin_role(self._course, self.remoteUser)
        elif is_enrolled(self._course, self.remoteUser):
            result = component.getMultiAdapter((self._course, self.remoteUser),
                                               ICourseInstanceEnrollment)
            if result is None:
                logger.warning('User enrolled but no enrollment record (%s) (%s)',
                               self.remoteUser,
                               ICourseCatalogEntry(self._course).ntiid)
        if result is None or IDeletedCourse.providedBy(result):
            msg = _('User does not have access to this course.')
            raise hexc.HTTPForbidden(msg)
        return result


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
class CourseTabPreferencesPathAdapter(Contained):

    __name__ = VIEW_COURSE_TAB_PREFERENCES

    def __init__(self, context, request):
        # Context is CourseInstance
        self.context = context
        self.request = request
        self.__parent__ = context


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=CourseTabPreferencesPathAdapter,
             request_method='GET',
             permission=nauth.ACT_READ)
class CourseTabPreferencesGetView(AbstractAuthenticatedView):

    def __call__(self):
        return ICourseTabPreferences(self.context.__parent__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=CourseTabPreferencesPathAdapter,
             request_method='PUT',
             permission=nauth.ACT_CONTENT_EDIT)
class CourseTabPreferencesUpdateView(UGDPutView):

    def _get_object_to_update(self):
        return ICourseTabPreferences(self.context.__parent__)


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInstance,
             request_method='GET',
             permission=nauth.ACT_READ)
class CourseGetView(GenericGetView):
    """
    Override the generic get view to ensure we do not adapt to a collection
    we do not want when GETting a course.
    """

    COLLECTION_TYPE = ICourseCollection


class _CompletionStats(object):

    def __init__(self):
        self.incomplete_ntiids = []
        self.unsuccessful_items = []
        self.successful_items = []

    def add_incomplete_ntiid(self, ntiid):
        self.incomplete_ntiids.append(ntiid)

    def add_successful_item(self, item):
        self.successful_items.append(item)

    def add_unsuccessful_item(self, item):
        self.unsuccessful_items.append(item)

    @property
    def incomplete(self):
        return len(self.incomplete_ntiids)

    @property
    def successful(self):
        return len(self.successful_items)

    @property
    def unsuccessful(self):
        return len(self.unsuccessful_items)


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             context=ICourseInstanceEnrollment,
             renderer='rest',
             name=VIEW_LESSON_COMPLETION_STATS)
class UserCourseLessonCompletionStatsView(AbstractAuthenticatedView):
    """
    A view to get completion stats (incomplete, completed_successfully, and
    completed_unsuccussfully) on each lesson for this contextual user.
    """

    @Lazy
    def _user(self):
        return IUser(self.context)

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    @Lazy
    def completable_item_providers(self):
        result = component.subscribers((self._course,),
                                       ICompletableItemProvider)
        return result

    @Lazy
    def completable_items(self):
        """
        A map of ntiid to completable items.
        """
        result = {}
        # pylint: disable=not-an-iterable
        for completable_provider in self.completable_item_providers:
            for item in completable_provider.iter_items(self._user):
                result[item.ntiid] = item
        return result

    @Lazy
    def required_items(self):
        """
        A map of ntiid to required completable items.
        """
        # For this view, if a course is not completable, no items are required.
        if not ICompletionContextCompletionPolicy(self._course, None):
            return {}
        return {x:y for x,y in self.completable_items.items()
                if is_item_required(y, self._course)}

    @Lazy
    def user_completed_items(self):
        """
        A map of ntiid to all user completed items.
        """
        result = {}
        for completed_provider in component.subscribers((self._user, self._course),
                                                        ICompletedItemProvider):
            for item in completed_provider.completed_items():
                result[item.item_ntiid] = item
        return result

    def _is_scheduled(self, obj):
        return  ICalendarPublishable.providedBy(obj) \
            and (obj.publishBeginning or obj.publishEnding)

    def _is_available(self, obj):
        return not IPublishable.providedBy(obj) \
            or obj.is_published(principal=self._user) \
            or self._is_scheduled(obj)

    def _process_item(self, ntiid, required_stats, unrequired_stats):
        stats = unrequired_stats
        if      ntiid in self.completable_items \
            and ntiid in self.required_items:
                stats = required_stats

        if ntiid not in self.user_completed_items:
            stats.add_incomplete_ntiid(ntiid)
        else:
            completed_item = self.user_completed_items[ntiid]
            if completed_item.Success:
                stats.add_successful_item(completed_item)
            else:
                stats.add_unsuccessful_item(completed_item)

    def _process_asset(self, asset, required_stats, unrequired_stats):
        # We could check if these items are visible etc, but
        # the RequiredItemProviders should handle all of that for us.
        # So we simply need to care if the item (or its target) is
        # required and/or is it completed.
        item = IConcreteAsset(asset, asset)
        target_ntiid = getattr(item, 'target', '')
        target = find_object_with_ntiid(target_ntiid)
        if ICompletableItem.providedBy(target):
            item_ntiid = getattr(target, 'ntiid', None)
            self._process_item(item_ntiid, required_stats, unrequired_stats)
        else:
            # Want to handle even non ICompletableItem objects here
            item_ntiid = getattr(item, 'ntiid', None)
            self._process_item(item_ntiid, required_stats, unrequired_stats)

    def _get_lesson_stats(self, lesson):
        required_stats = _CompletionStats()
        unrequired_stats = _CompletionStats()
        for group in lesson or ():
            for item in group or ():
                self._process_asset(item, required_stats, unrequired_stats)
                children = getattr(item, 'Items', None)
                for child in children or ():
                    self._process_asset(child, required_stats, unrequired_stats)
        return required_stats, unrequired_stats

    def _build_outline_stats(self):
        """
        Returns:

        [{<node_ntiid>: [{'LessonNTIID': node.LessonOverviewNTIID,
                         'IncompleteCount': incomplete,
                         'UnsuccessfulCount': unsuccessful,
                         'SuccessfulCount': successful,
                         'UnrequiredIncompleteCount': u_incomplete,
                         'UnrequiredUnsuccessfulCount': u_unsuccessful,
                         'UnrequiredSuccessfulCount': u_successful},
                         ...},
        ...]
        """
        result = []
        def _recur(node, node_list):
            if ICourseOutlineContentNode.providedBy(node):
                lesson = find_object_with_ntiid(node.LessonOverviewNTIID)
                if      lesson is not None \
                    and self._is_available(lesson):
                    required_stats, unrequired_stats = self._get_lesson_stats(lesson)
                    node_list.append({'LessonNTIID': node.LessonOverviewNTIID,
                                      'IncompleteCount': required_stats.incomplete,
                                      'UnsuccessfulCount': required_stats.unsuccessful,
                                      'SuccessfulCount': required_stats.successful,
                                      'IncompleteNTIIDs': required_stats.incomplete_ntiids,
                                      'SuccessfulItems': required_stats.successful_items,
                                      'UnSuccessfulItems': required_stats.unsuccessful_items,
                                      'UnrequiredIncompleteNTIIDs': unrequired_stats.incomplete_ntiids,
                                      'UnrequiredSuccessfulItems': unrequired_stats.successful_items,
                                      'UnrequiredUnSuccessfulItems': unrequired_stats.unsuccessful_items,
                                      'UnrequiredIncompleteCount': unrequired_stats.incomplete,
                                      'UnrequiredUnsuccessfulCount': unrequired_stats.unsuccessful,
                                      'UnrequiredSuccessfulCount': unrequired_stats.successful})
            child_node_list = []
            for child_node in node.values():
                _recur(child_node, child_node_list)
            if child_node_list:
                try:
                    node_list.append({node.ntiid: child_node_list})
                except AttributeError:
                    # CourseOutline
                    node_list.extend(child_node_list)
        _recur(self._course.Outline, result)
        return result

    def _build_assignment_stats(self):
        required_stats = _CompletionStats()
        unrequired_stats = _CompletionStats()
        for ntiid, item in self.completable_items.items():
            if not IQAssignment.providedBy(item):
                continue
            self._process_item(ntiid, required_stats, unrequired_stats)
        return required_stats, unrequired_stats

    def _check_access(self):
        if      not self.remoteUser == self._user \
            and not is_course_instructor(self._course, self.remoteUser) \
            and not is_admin_or_site_admin(self.remoteUser):
            raise hexc.HTTPForbidden()

    def __call__(self):
        """
        We want to gather stats for outline nodes and ideally, assignments not
        in the course outline.

        The required-item provider and completed item provider should we be all
        we need.

        We'll skip lessons that are unpublished.
        """
        self._check_access()
        result = LocatedExternalDict()
        required_stats, unrequired_stats = self._build_assignment_stats()
        result['Assignments'] = {'IncompleteCount': required_stats.incomplete,
                                 'UnsuccessfulCount': required_stats.unsuccessful,
                                 'SuccessfulCount': required_stats.successful,
                                 'IncompleteNTIIDs': required_stats.incomplete_ntiids,
                                 'SuccessfulItems': required_stats.successful_items,
                                 'UnSuccessfulItems': required_stats.unsuccessful_items,
                                 'UnrequiredIncompleteNTIIDs': unrequired_stats.incomplete_ntiids,
                                 'UnrequiredSuccessfulItems': unrequired_stats.successful_items,
                                 'UnrequiredUnSuccessfulItems': unrequired_stats.unsuccessful_items,
                                 'UnrequiredIncompleteCount': unrequired_stats.incomplete,
                                 'UnrequiredUnsuccessfulCount': unrequired_stats.unsuccessful,
                                 'UnrequiredSuccessfulCount': unrequired_stats.successful}
        result['Outline'] = self._build_outline_stats()
        return result

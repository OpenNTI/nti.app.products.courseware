#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from numbers import Number

from zope import component
from zope import interface

from zope.annotation.interfaces import IAnnotations

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.intid.interfaces import IIntIds

from zope.traversing.interfaces import IPathAdapter

import BTrees

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from pyramid.view import view_config
from pyramid.view import view_defaults

from pyramid.threadlocal import get_current_request

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.interfaces import ACT_VIEW_ROSTER
from nti.app.products.courseware.interfaces import ACT_VIEW_ACTIVITY

from nti.app.products.courseware.interfaces import ICourseInstanceActivity
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICoursePagesContainerResource

from nti.app.products.courseware.utils import get_enrollment_options

from nti.app.products.courseware.views import MessageFactory as _

from nti.app.products.courseware.views import VIEW_CONTENTS
from nti.app.products.courseware.views import VIEW_COURSE_ACTIVITY
from nti.app.products.courseware.views import VIEW_USER_COURSE_ACCESS
from nti.app.products.courseware.views import VIEW_COURSE_ENROLLMENT_ROSTER

from nti.app.renderers.interfaces import IResponseCacheController

from nti.appserver.interfaces import IIntIdUserSearchPolicy

from nti.appserver.pyramid_authorization import has_permission
from nti.appserver.ugd_edit_views import ContainerContextUGDPostView
from nti.appserver.ugd_query_views import Operator
from nti.appserver.ugd_query_views import _combine_predicate
from nti.appserver.relevant_ugd_views import _RelevantUGDView

from nti.common.string import is_true

from nti.contenttypes.courses.administered import get_course_admin_role

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.contenttypes.presentation.lesson import get_constraint_satisfied_time

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import is_admin_or_content_admin

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import ILocatedExternalSequence

from nti.externalization.externalization import to_external_object
from nti.externalization.externalization import decorate_external_mapping

from nti.externalization.oids import to_external_ntiid_oid as toExternalOID

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import alias

from nti.publishing.interfaces import IPublishable

from nti.zodb.containers import bit64_int_to_time
from nti.zodb.containers import time_to_64bit_int

OID = StandardExternalFields.OID
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS

union_operator = Operator.union


class PreResponseOutlineContentsCacheController(object):

    def __call__(self, last_modified, system):
        request = system['request']
        self.remote_user = request.authenticated_userid
        response = request.response
        response.last_modified = last_modified
        obj = object()
        cache_controller = IResponseCacheController(obj)
        # Context is ignored
        return cache_controller(obj, system)


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
        return has_permission(nauth.ACT_CONTENT_EDIT, self.context, self.request)

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
        return not omit_unpublished

    def _is_published(self, item):
        """
        Node is published or we're an editor asking for unpublished.
        """
        return not IPublishable.providedBy(item) \
            or item.is_published() \
            or (self.show_unpublished
                and self._is_course_editor)

    _is_visible = _is_published

    def _get_node_lesson(self, node):
        lesson_ntiid = node.LessonOverviewNTIID
        lesson = find_object_with_ntiid(lesson_ntiid) if lesson_ntiid else None
        return lesson

    @Lazy
    def last_mod(self):
        """
        Derive our last mod time by traversing the tree. To do this correctly,
        we would need to pre-determine which nodes are visible to our user
        (is_published). We should cache that check.
        """
        def update_last_mod(new_last_mod):
            update_last_mod.last_mod = max(
                update_last_mod.last_mod, new_last_mod)
        update_last_mod.last_mod = self.context.lastModified

        def _recur(the_nodes):
            for node in the_nodes:
                update_last_mod(node.lastModified)
                # Must also take into account publication changes.
                if IPublishable.providedBy(node):
                    last_modified_time = node.publishLastModified
                    update_last_mod(last_modified_time)

                lesson = self._get_node_lesson(node)
                # If this node has a lesson, it may have been gated.
                # If the constraints have been satisfied, we'll need
                # to use that time when considered the contents available.
                if lesson is not None:
                    constraints_satisfied_time = get_constraint_satisfied_time(
                                                        self.remoteUser, lesson)
                    if constraints_satisfied_time is not None:
                        update_last_mod(constraints_satisfied_time)
                _recur(node.values())

        _recur(self.context.values())
        return update_last_mod.last_mod

    def pre_caching(self):
        # Since we externalize ourselves, attempt to return early if we
        # can. This call can be extensive to externalize now that we have
        # massive course outlines in the wild.
        cache_controller = PreResponseOutlineContentsCacheController()
        cache_controller(self.last_mod, {'request': self.request})

    def _is_contents_available(self, item):
        """
        Lesson is available if published or if we're an editor.
        """
        lesson = self._get_node_lesson(item)
        # Returns True if lesson is None (implying outline node)
        result = self._is_published(lesson)
        return result

    def externalize_node_contents(self, node):
        """
        Recursively externalize our `node` contents, setting the
        response lastMod based on the given node.
        """
        values = node.values()
        result = ILocatedExternalSequence([])

        def _recur(the_list, the_nodes):
            for node in the_nodes:
                if not self._is_visible(node):
                    continue

                # We used to set this based on our outline itself, but now that
                # items can be modified independently, we need to check our
                # children.
                ext_node = to_external_object(node)
                if self._is_contents_available(node):
                    ext_node['contents'] = _recur([], node.values())
                else:
                    # Some clients drive behavior based on this attr.
                    ext_node.pop('ContentNTIID', None)
                # Pretty pointless to send these
                ext_node.pop(OID, None)
                the_list.append(ext_node)
            return the_list

        _recur(result, values)
        result.__name__ = self.request.view_name
        result.__parent__ = node
        response = self.request.response
        response.last_modified = self.last_mod
        return result

    def __call__(self):
        #self.pre_caching()
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

    def __init__(self, course, request):
        self.__parent__ = course
        self.__name__ = VIEW_COURSE_ENROLLMENT_ROSTER

    course = alias('__parent__')

    def __getitem__(self, username):
        username = username.lower()
        # XXX: We can do better than this interface now
        enrollments_iter = ICourseEnrollments(
            self.__parent__).iter_enrollments()
        for record in enrollments_iter:
            user = IUser(record)
            if user.username.lower() == username:
                enrollment = component.getMultiAdapter((self.__parent__, record),
                                                       ICourseInstanceEnrollment)
                enrollment.CourseInstance = None
                return enrollment

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
            username``.

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

    def __call__(self):
        request = self.request
        context = request.context.course
        course = context

        result = LocatedExternalDict()
        result.__name__ = request.view_name
        result.__parent__ = course
        items = result[ITEMS] = []

        enrollments_iter = ICourseEnrollments(course).iter_enrollments()

        filter_name = self.request.params.get('filter')
        sort_name = self.request.params.get('sortOn')
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
                user = IUser(record)
                parts = IFriendlyNamed(user).get_searchable_realname_parts()
                if not parts:
                    return ''
                parts = reversed(parts)  # last name first
                return ' '.join(parts).lower()

            enrollments_iter = sorted(enrollments_iter,
                                      key=_key,
                                      reverse=sort_reverse)
        elif sort_name == 'username':
            def _key(x): return IUser(x).username
            enrollments_iter = sorted(enrollments_iter,
                                      key=_key,
                                      reverse=sort_reverse)
        elif sort_name:  # pragma: no cover
            # We're not silently ignoring because in the past
            # we've had clients send in the wrong value for a long time
            # before anybody noticed
            raise hexc.HTTPBadRequest("Unsupported sort option")

        items.extend((component.getMultiAdapter((course, x),
                                                ICourseInstanceEnrollment)
                      for x in enrollments_iter))

        result['TotalItemCount'] = len(result['Items'])
        result['FilteredTotalItemCount'] = result['TotalItemCount']

        # We could theoretically be more efficient with the user of
        # the IEnumerableEntity container and the scopes, especially
        # if we did that FIRST, before getting the enrollments, and
        # paging that range of usernames, and doing the entity
        # username search on the intid set it returns. However, this
        # is good enough for now. Sorting is maintained from above.
        # Note that it will blow up once we have non-legacy courses.

        if filter_name == 'LegacyEnrollmentStatusForCredit':
            items = [
                x for x in items if x.LegacyEnrollmentStatus == 'ForCredit'
            ]
            result['FilteredTotalItemCount'] = len(items)
        elif filter_name == 'LegacyEnrollmentStatusOpen':
            items = [
                x for x in items if x.LegacyEnrollmentStatus == 'Open'
            ]
            result['FilteredTotalItemCount'] = len(items)
        elif filter_name:  # pragma: no cover
            raise hexc.HTTPBadRequest("Unsupported filteroption")

        if username_search_term:
            matched_items = []
            policy = component.getAdapter(self.remoteUser,
                                          IIntIdUserSearchPolicy,
                                          name='comprehensive')
            id_util = component.getUtility(IIntIds)
            matched_ids = policy.query_intids(username_search_term.lower())
            for x in items:
                uid = id_util.queryId(IUser(x, None))
                if uid is not None and uid in matched_ids:
                    matched_items.append(x)
            items = matched_items
            result['FilteredTotalItemCount'] = len(items)

        self._batch_tuple_iterable(result, items,
                                   selector=lambda x: x)

        # NOTE: Rendering the same CourseInstance over and over is hugely
        # expensive, and massively bloats the response...77 students
        # can generate 12MB of response. So we don't include the course
        # instance
        for i in result[ITEMS]:
            i.CourseInstance = None

        # TODO: We have no last modified for this
        return result


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def CourseActivityPathAdapter(context, request):
    return ICourseInstanceActivity(context)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseCatalogEntry, IRequest)
def CatalogEntryActivityPathAdapter(context, request):
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
        result['Last Modified'] = last_modified
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

    def __init__(self, request, the_user=None, the_ntiid=None):
        self.request = request
        super(_RelevantUGDView, self).__init__(request,
                                               the_user=self.remoteUser,
                                               the_ntiid=self.context.ntiid)

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


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             name=VIEW_USER_COURSE_ACCESS,
             request_method='GET',
             context=ICourseInstance,
             permission=nauth.ACT_READ)
class UserCourseAccessView(AbstractAuthenticatedView):
    """
    A view that returns the preferred user access to the course context. This
    may be an administrative role or an enrollment record. We should mimic what
    is returned by the course workspaces.
    """

    @Lazy
    def _is_admin(self):
        return is_admin_or_content_admin(self.remoteUser) \
            or is_course_instructor_or_editor(self.context, self.remoteUser)

    def __call__(self):
        result = None
        if self._is_admin:
            result = get_course_admin_role(self.context, self.remoteUser)
        elif is_enrolled(self.context, self.remoteUser):
            result = component.getMultiAdapter((self.context, self.remoteUser),
                                               ICourseInstanceEnrollment)
            if result is None:
                logger.warn('User enrolled but no enrollment record (%s) (%s)',
                            self.remoteUser,
                            ICourseCatalogEntry(self.context).ntiid)
        if result is None:
            raise hexc.HTTPForbidden(
                _('User does not have access to this course.'))
        return result

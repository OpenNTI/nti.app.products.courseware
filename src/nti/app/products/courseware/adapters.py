#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

import itertools

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from pyramid.interfaces import IRequest

from ZODB.interfaces import IConnection

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from zope.annotation.interfaces import IAnnotations

from zope.cachedescriptors.property import Lazy

from zope.traversing.interfaces import IPathAdapter

from nti.app.products.integration.workspaces import IntegrationCollection

from nti.app.authentication import get_remote_user

from nti.app.externalization.error import raise_json_error

from nti.app.products.courseware import USER_ENROLLMENT_LAST_MODIFIED_KEY

from nti.app.products.courseware._outline_path import OutlinePathFactory

from nti.app.products.courseware.enrollment import EnrollmentOptionContainer

from nti.app.products.courseware.interfaces import IEnrollmentOptionContainer
from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance
from nti.app.products.courseware.interfaces import ILegacyCourseConflatedContentPackageUsedAsCourse

from nti.appserver.context_providers import get_joinable_contexts
from nti.appserver.context_providers import get_top_level_contexts

from nti.appserver.interfaces import ForbiddenContextException

from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ILibraryPathLastModifiedProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider
from nti.appserver.interfaces import ITrustedTopLevelContainerContextProvider

from nti.appserver.pyramid_authorization import is_readable
from nti.appserver.pyramid_authorization import has_permission

from nti.assessment.interfaces import IQEvaluation

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.contenttypes.courses.common import get_course_site_name

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES

from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseOutlineNode
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseOutlineNodes
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import is_course_instructor
from nti.contenttypes.courses.utils import get_enrollment_catalog
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import get_content_outline_nodes
from nti.contenttypes.courses.utils import is_course_instructor_or_editor
from nti.contenttypes.courses.utils import content_unit_to_courses as indexed_content_unit_to_courses

from nti.contenttypes.presentation.interfaces import INTIPollRef
from nti.contenttypes.presentation.interfaces import INTITimeline
from nti.contenttypes.presentation.interfaces import INTISurveyRef
from nti.contenttypes.presentation.interfaces import INTIQuestionRef
from nti.contenttypes.presentation.interfaces import INTITimelineRef
from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRef
from nti.contenttypes.presentation.interfaces import IItemAssetContainer
from nti.contenttypes.presentation.interfaces import INTIRelatedWorkRefPointer

from nti.coremetadata.interfaces import ILastSeenProvider
from nti.coremetadata.interfaces import IContainerContext
from nti.coremetadata.interfaces import IContextLastSeenContainer

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IContained
from nti.dataserver.interfaces import IHighlight
from nti.dataserver.interfaces import IAccessProvider
from nti.dataserver.interfaces import IUserGeneratedData

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

is_instructor = is_course_instructor  # BWC

ENROLLMENT_OPTION_CONTAINER_KEY = 'nti.contenttypes.courses.interfaces.IEnrollmentOptionContainer'

logger = __import__('logging').getLogger(__name__)


#: Misc


def _is_user_enrolled(user, course):
    # Enrolled or instructor
    result = user is not None \
         and course is not None \
         and (is_enrolled(course, user) or is_course_instructor_or_editor(course, user))
    return result


#: Outline adapters


@component.adapter(IPresentationAsset)
@interface.implementer(ICourseOutlineNodes)
def _asset_to_nodes(asset, user=None):
    result = find_interface(asset, ICourseOutlineNode, strict=False)
    if result is None:
        result = []
        catalog = get_library_catalog()
        for container in catalog.get_containers(asset) or ():
            obj = find_object_with_ntiid(container)
            if IItemAssetContainer.providedBy(obj):
                node = find_interface(asset, ICourseOutlineNode, strict=False)
                course = find_interface(result, ICourseInstance, strict=False)
                if      node is not None \
                    and (user is None or _is_user_enrolled(user, course)):
                    result.append(node)
    else:
        course = find_interface(result, ICourseInstance, strict=False)
        if (user is not None and not _is_user_enrolled(user, course)):
            result = ()
        else:
            result = (result,)
    return result


@component.adapter(IContentUnit)
@interface.implementer(ICourseOutlineNodes)
def _contentunit_to_nodes(obj, user=None):
    result = set()
    sites = get_component_hierarchy_names()
    nodes = get_content_outline_nodes(obj.ntiid)
    if nodes:  # easy case .. direct node
        for node in nodes:
            course = find_interface(node, ICourseInstance, strict=False)
            if user is None and get_course_site_name(course) in sites:
                result.add(node)
            elif _is_user_enrolled(user, course):
                result.add(node)
    else:
        catalog = get_library_catalog()
        intids = component.getUtility(IIntIds)
        DOCKET_PROVIDED = (INTIRelatedWorkRef, INTITimeline)
        REF_PROVIDED = (INTIRelatedWorkRefPointer, INTITimelineRef)

        # search for all dockets that point to the container
        for docket in catalog.search_objects(sites=sites,
                                             intids=intids,
                                             target=obj.ntiid,
                                             provided=DOCKET_PROVIDED):

            # search for all pointers that point to the docket
            objs = catalog.search_objects(sites=sites,
                                          intids=intids,
                                          target=docket.ntiid,
                                          provided=REF_PROVIDED)

            # find node and check
            for ref in itertools.chain(objs or (), (docket,)):
                node = find_interface(ref, ICourseOutlineNode, strict=False)
                course = find_interface(node, ICourseInstance, strict=False)
                if node is not None and (user is None or _is_user_enrolled(user, course)):
                    result.add(node)
    return result or ()


@component.adapter(IContained)
@component.adapter(IUserGeneratedData)
@interface.implementer(ICourseOutlineNodes)
def _contained_to_nodes(obj, user=None):
    containerId = getattr(obj, 'containerId', None)
    container = find_object_with_ntiid(containerId) if containerId else None
    if IContentUnit.providedBy(container):
        return _contentunit_to_nodes(container, user)
    return ()


@component.adapter(IQEvaluation)
@interface.implementer(ICourseOutlineNodes)
def _evaluation_to_nodes(obj, user=None):
    result = []
    catalog = get_library_catalog()
    intids = component.getUtility(IIntIds)
    sites = get_component_hierarchy_names()
    provided = (INTIPollRef, INTISurveyRef, INTIQuestionRef,
                INTIQuestionSetRef, INTIAssignmentRef)

    # search for all dockets that point to the container
    for ref in catalog.search_objects(sites=sites,
                                      intids=intids,
                                      target=obj.ntiid,
                                      provided=provided):
        node = find_interface(ref, ICourseOutlineNode, strict=False)
        course = find_interface(node, ICourseInstance, strict=False)
        if node is not None and (user is None or _is_user_enrolled(user, course)):
            result.append(node)
    return result or ()


#: Course adapters


@interface.implementer(IContentPackageBundle)
@component.adapter(ILegacyCommunityBasedCourseInstance)
def _legacy_course_to_content_package_bundle(course):
    return course.ContentPackageBundle


@component.adapter(IContentCourseInstance)
@interface.implementer(IContentPackageBundle)
def _course_content_to_package_bundle(course):
    return course.ContentPackageBundle


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IContentPackageBundle)
def _entry_to_content_package_bundle(entry):
    course = ICourseInstance(entry, None)
    return IContentPackageBundle(course, None)


@interface.implementer(ICourseInstance)
@component.adapter(ILegacyCourseConflatedContentPackageUsedAsCourse)
def _course_content_package_to_course(package):
    # Both the catalog entry and the content package are supposed to
    # be non-persistent (in the case we actually get a course) or the
    # course doesn't exist (in the case that the package is persistent
    # and installed in a sub-site, which shouldn't happen with this
    # registration, though could if we used a plain
    # ConflatedContentPackage), so it should be safe to cache this on
    # the package. Be extra careful though, just in case.
    course = None
    cache_name = '_v_course_content_package_to_course'
    course_intid = getattr(package, cache_name, cache_name)
    intids = component.getUtility(IIntIds)

    if course_intid is not cache_name and isinstance(course_intid, int):
        course = intids.queryObject(course_intid)

    if course is not None:
        return course

    # We go via the defined adapter from the catalog entry,
    # which we should have directly cached
    try:
        # pylint: disable=protected-access
        entry = package._v_global_legacy_catalog_entry
    except AttributeError:
        logger.warning("Consistency issue? No attribute on global package %s",
                       package)
        entry = None

    course = ICourseInstance(entry, None)
    course_intid = intids.queryId(course, None)
    setattr(package, cache_name, course_intid)
    return course


def content_unit_to_courses(unit, include_sub_instances=True):
    # First, try the true legacy case. This involves
    # a direct mapping between courses and a catalog entry. It may be
    # slightly more reliable, but only works for true legacy cases.
    package = find_interface(unit, ILegacyCourseConflatedContentPackageUsedAsCourse,
                             strict=False)
    if package is not None:
        result = ICourseInstance(package, None)
        if result is not None:
            return (result,)

    result = indexed_content_unit_to_courses(unit, include_sub_instances)
    return result


@component.adapter(IContentUnit)
@interface.implementer(ICourseInstance)
def _content_unit_to_course(unit):
    # get all courses, don't include sections
    courses = content_unit_to_courses(unit, False)
    # We probably need to check and see who's enrolled
    # to find the most specific course instance to return?
    # As it stands, we promise to return only a root course,
    # not a subinstance (section)
    # Warning!!! This requires a one-to-one mapping
    return courses[0] if courses else None


@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit, IUser)
def _content_unit_and_user_to_course(unit, user):
    # get all courses
    courses = content_unit_to_courses(unit, True)
    for instance in courses or ():
        if _is_user_enrolled(user, instance):
            return instance
    # nothing found return first course
    return courses[0] if courses else None


#: Context adapters


def _get_top_level_contexts(obj):
    results = set()
    top_level_contexts = get_top_level_contexts(obj)
    for top_level_context in top_level_contexts:
        if     ICourseInstance.providedBy(top_level_context) \
            or ICourseCatalogEntry.providedBy(top_level_context):
            results.add(top_level_context)
    return results


def _is_catalog_entry_visible(entry):
    return  entry is not None \
        and not INonPublicCourseInstance.providedBy(entry) \
        and is_readable(entry)


def _get_valid_course_context(course_contexts):
    """
    Validate course context access for remote_user, returning
    catalog entries otherwise.
    """
    if not course_contexts:
        return ()

    if ICourseInstance.providedBy(course_contexts):
        course_contexts = (course_contexts,)

    courses = []
    catalog_entries = []
    user = get_remote_user()
    for course_context in course_contexts:
        if ICourseCatalogEntry.providedBy(course_context):
            if _is_catalog_entry_visible(course_context):
                catalog_entries.append(course_context)
        elif    not _is_user_enrolled(user, course_context) \
            and not has_permission(ACT_CONTENT_EDIT, course_context):
            # Not enrolled and not an editor, get catalog entry.
            catalog_entry = ICourseCatalogEntry(course_context, None)
            # We only want to add publicly available entries.
            if _is_catalog_entry_visible(catalog_entry):
                catalog_entries.append(catalog_entry)
        else:
            courses.append(course_context)

    if not courses and user is not None:
        # For video and related work in parent course, their containers only contain parent course,
        # but we hope that a section course should also be returned for users who enroll in the section course.
        # TODO: probably need a better way to deal with, for parent course may have lots of section courses?
        for course in course_contexts:
            if ICourseSubInstance.providedBy(course):
                continue
            for subinstance in get_course_subinstances(course):
                if     _is_user_enrolled(user, subinstance) \
                    or has_permission(ACT_CONTENT_EDIT, subinstance):
                    # Find the first enrolled course.
                    courses.append(subinstance)
                    break
            if courses:
                break

    # If we only have catalog entries, we should raise.
    # Otherwise, make sure our courses are returned first.
    if not courses and catalog_entries:
        raise ForbiddenContextException(catalog_entries)

    return courses + catalog_entries


get_valid_course_context = _get_valid_course_context


@component.adapter(interface.Interface)
@interface.implementer(IJoinableContextProvider)
def _catalog_entry_from_container_object(obj):
    return get_joinable_contexts(obj)


def _get_target_ntiid(obj):
    target_ntiid = getattr(obj, 'ntiid', None)
    # Content cards are pseudo objects, so get
    # the nearest available ntiid.
    if not target_ntiid:
        try:
            target_ntiid = obj.path[-1].ntiid
        except AttributeError:
            pass
    if not target_ntiid:
        raise_json_error(get_current_request(),
                         hexc.HTTPUnprocessableEntity,
                         {
                             'message': 'Unexpected object %s' % type(obj),
                         },
                         None)
    return target_ntiid


@interface.implementer(IHierarchicalContextProvider)
@component.adapter(ICourseInstance, interface.Interface)
class CourseHierarchyPathProvider(object):

    def __init__(self, course, obj):
        self.obj = obj
        self.course = course

    def get_context_paths(self, context=None):
        target_ntiid = _get_target_ntiid(self.obj)
        # Typically, we get a user enrolled course here, but validate.
        context_courses = _get_valid_course_context(self.course)
        results = []
        if context_courses:
            course = context_courses[0]
            results = OutlinePathFactory(course, target_ntiid)()
            results = (results,) if results else results
        return results


def _get_courses_from_container(obj, user=None):
    results = set()
    if ICourseInstance.providedBy(obj):
        results.add(obj)
        return results

    catalog = get_library_catalog()
    if catalog:
        containers = catalog.get_containers(obj)
        for container in containers:
            course = None
            container = find_object_with_ntiid(container)
            if user is not None:
                course = component.queryMultiAdapter((container, user),
                                                     ICourseInstance)
            if course is None:
                course = ICourseInstance(container, None)

            if course is not None:
                results.add(course)
    if not results:
        courses = content_unit_to_courses(obj, True)
        results.update(courses)
    return results


def get_container_context(obj):
    """
    Attempt to get the root context from the object itself.
    """
    result = None
    container_context = IContainerContext(obj, None)
    if container_context:
        context_id = container_context.context_id
        container = find_object_with_ntiid(context_id)
        if ICourseInstance.providedBy(container):
            result = container
    return result


@component.adapter(IHighlight, IUser)
@component.adapter(IContentUnit, IUser)
@component.adapter(IPresentationAsset, IUser)
@interface.implementer(IHierarchicalContextProvider)
class UserCourseHierarchyPathProvider(object):

    def __init__(self, obj, user):
        self.obj = obj
        self.user = user

    def get_context_paths(self, context=None):
        course = context
        if ICourseInstance.providedBy(course):
            container_courses = (course,)
        else:
            container_courses = _get_courses_from_container(self.obj, self.user)
        possible_courses = _get_valid_course_context(container_courses)
        target_ntiid = _get_target_ntiid(self.obj)
        results = []
        course_only_results = []
        catalog_entries = set()
        caught_exception = None
        for course in possible_courses:
            if ICourseCatalogEntry.providedBy(course):
                catalog_entries.add(course)
            else:
                try:
                    nodes = OutlinePathFactory(course, target_ntiid)()
                except ForbiddenContextException as e:
                    # Catch and see if other courses have an acceptable path.
                    caught_exception = e
                else:
                    if nodes:
                        # Great, we found a path, finish with first one.
                        results.append(nodes)
                        break
                    else:
                        course_only_results.append((course,))

        if not results and course_only_results:
            # No actual results, use what we have.
            results = course_only_results

        if not results:
            if caught_exception is not None:
                # No path found and this exception indicates the path goes through
                # an unpublished object.
                # pylint: disable=raising-bad-type
                raise caught_exception

            # This means are content only exists in catalog entries
            # our user cannot currently reach.
            if catalog_entries:
                raise ForbiddenContextException(catalog_entries)
        return results


def _get_preferred_course(found_course):
    """
    Prefer any enrolled subinstances to a board object found
    at a top-level course instance.
    """
    # Do we need to do anything different for instructors?
    user = get_remote_user()
    if ICourseSubInstance.providedBy(found_course) or user is None:
        return found_course

    enrolled_courses = []
    catalog = get_enrollment_catalog()
    intids = component.getUtility(IIntIds)
    site_names = get_component_hierarchy_names()
    query = {
        IX_SITE: {'any_of': site_names},
        IX_USERNAME: {'any_of': (user.username,)}
    }
    for uid in catalog.apply(query) or ():
        context = intids.queryObject(uid)
        if ICourseInstanceEnrollmentRecord.providedBy(context):
            course = ICourseInstance(context, None)
            if course is not None:
                enrolled_courses.append(course)

    if found_course not in enrolled_courses:
        for subinstance in get_course_subinstances(found_course):
            if subinstance in enrolled_courses:
                return subinstance
    return found_course


def _find_lineage_course(obj, trusted=False):
    course = find_interface(obj, ICourseInstance, strict=False)
    if course is not None:
        course = _get_preferred_course(course)
        if trusted:
            catalog_entry = ICourseCatalogEntry(course, None)
            results = (catalog_entry,) if catalog_entry is not None else ()
        else:
            results = _get_valid_course_context(course)
        return results


def _catalog_entries_from_courses(courses):
    results = []
    for course in courses or ():
        catalog_entry = ICourseCatalogEntry(course, None)
        if catalog_entry is not None:
            results.append(catalog_entry)
    return results


@component.adapter(IPost)
@component.adapter(ITopic)
@component.adapter(IForum)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_forum_obj(obj):
    return _find_lineage_course(obj)


@component.adapter(IPost, IUser)
@component.adapter(ITopic, IUser)
@component.adapter(IForum, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_forum_obj_and_user(obj, *unused_args, **unused_kwargs):
    return _find_lineage_course(obj)


@component.adapter(IPost)
@component.adapter(ITopic)
@component.adapter(IForum)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_forum_obj(obj):
    return _find_lineage_course(obj, True)


@component.adapter(IContentUnit)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _courses_from_package(obj):
    # We could use the container index.
    courses = content_unit_to_courses(obj, True)
    return _get_valid_course_context(courses)


@component.adapter(IContentUnit)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_package(obj):
    courses = content_unit_to_courses(obj, True)
    return _catalog_entries_from_courses(courses)


@component.adapter(IContentUnit, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_package_and_user(obj, unused_user):
    courses = content_unit_to_courses(obj, True)
    return _get_valid_course_context(courses)


@component.adapter(ICourseInstance, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _top_level_context_from_course_and_user(obj, unused_user):
    return _get_valid_course_context(obj)


@component.adapter(ICourseInstance)
@interface.implementer(ITopLevelContainerContextProvider)
def _top_level_context_from_course(obj):
    return _get_valid_course_context(obj)


def __courses_from_obj_and_user(obj, user=None):
    if IHighlight.providedBy(obj):
        obj_ntiid = obj.containerId
        container_obj = find_object_with_ntiid(obj_ntiid)
        if container_obj is not None:
            obj = container_obj
    container_courses = _get_courses_from_container(obj, user)
    return container_courses


def _top_level_context_from_obj_and_user(obj, user=None):
    courses = __courses_from_obj_and_user(obj, user)
    return _get_valid_course_context(courses)


def _trusted_top_level_context(obj, user=None):
    courses = __courses_from_obj_and_user(obj, user)
    return _catalog_entries_from_courses(courses)


@component.adapter(IHighlight, IUser)
@component.adapter(IPresentationAsset, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_obj_and_user(obj, user):
    return _top_level_context_from_obj_and_user(obj, user)


@component.adapter(IHighlight)
@component.adapter(IPresentationAsset)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_obj(obj):
    return _top_level_context_from_obj_and_user(obj)


@component.adapter(IHighlight)
@component.adapter(IPresentationAsset)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_obj(obj):
    return _trusted_top_level_context(obj)


@component.adapter(IUser)
@interface.implementer(ILibraryPathLastModifiedProvider)
def _enrollment_last_modified(user):
    # We didn't migrate this, so this annotation may not be
    # completely accurate. That should be ok since
    # we know we're only using this for cache invalidation.
    annotations = IAnnotations(user)
    return annotations.get(USER_ENROLLMENT_LAST_MODIFIED_KEY, 0)


#: Request adapters


@component.adapter(IRequest)
@interface.implementer(ICourseInstance)
def _course_from_request(request):
    """
    We may have our course instance stashed in the request if it
    was in our path.
    """
    try:
        return request.course_traversal_context
    except AttributeError:
        return None


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IAccessProvider)
class _CourseAccessProvider(object):
    """
    Grants and removes access to a course. This is simply a passthrough
    to :class:`ICourseEnrollmentManager` operations.
    """

    def __init__(self, context):
        self.context = context

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def entry(self):
        return ICourseCatalogEntry(self.context)

    @Lazy
    def entry_ntiid(self):
        # pylint: disable=no-member
        return self.entry.ntiid

    def _scope_lookup(self, scope_name):
        """
        Case insensitive lookup of given scope.
        """
        scope_dict = dict()
        for scope in ENROLLMENT_SCOPE_NAMES:
            scope_dict[scope.lower()] = scope
        scope_name = scope_name.lower()
        # Should probably raise if we have a non-existent scope.
        return scope_dict.get(scope_name, ES_PUBLIC)

    def grant_access(self, entity, access_context=None):
        """
        Enrolls the entity into the course. Defaults to public enrollment.
        """
        scope = ES_PUBLIC
        if access_context:
            scope = self._scope_lookup(access_context)
        manager = ICourseEnrollmentManager(self.course)
        # pylint: disable=redundant-keyword-arg
        result = manager.enroll(entity, scope=scope)
        logger.info("User enrolled in course (%s) (%s) (scope=%s)",
                    entity.username, self.entry_ntiid, scope)
        return result

    def remove_access(self, entity):
        """
        Unenrolls the user from the course.
        """
        manager = ICourseEnrollmentManager(self.course)
        # pylint: disable=too-many-function-args
        result = manager.drop(entity)
        logger.info("User dropped course (%s) (%s)",
                    entity.username, self.entry_ntiid)
        return result


@component.adapter(ICourseInstance)
@component.adapter(ICourseCatalogEntry)
@interface.implementer(IAccessProvider)
def _course_access_factory(course_or_entry):
    course = ICourseInstance(course_or_entry, None)
    if      course is not None \
        and not IDeletedCourse.providedBy(course):
        return _CourseAccessProvider(course)


@component.adapter(ICourseInstance)
@interface.implementer(IEnrollmentOptionContainer)
def enrollment_container(context):
    course = ICourseInstance(context)
    result = None
    annotations = IAnnotations(course)
    try:
        result = annotations[ENROLLMENT_OPTION_CONTAINER_KEY]
    except KeyError:
        result = EnrollmentOptionContainer()
        annotations[ENROLLMENT_OPTION_CONTAINER_KEY] = result
        # result.__name__ = ENROLLMENT_OPTION_CONTAINER_KEY
        result.__parent__ = course
        # Deterministically add to our course db. Sectioned courses would give
        # us multiple db error for some reason.
        # pylint: disable=too-many-function-args
        IConnection(course).add(result)
    return result


@component.adapter(IUser, ICourseInstance)
@interface.implementer(ILastSeenProvider)
class _CourseLastSeenProvider(object):

    def __init__(self, user, context):
        self.user = user
        self.context = context

    @Lazy
    def lastSeenTime(self):
        _dt = None
        # pylint: disable=too-many-function-args
        container = IContextLastSeenContainer(self.user, None)
        if container:
            ntiid = getattr(self.context, 'ntiid', None)
            _dt = container.get_timestamp(ntiid) if ntiid else None

        if not _dt:
            # Enrollment date.
            enrollments = ICourseEnrollments(self.context)
            record = enrollments.get_enrollment_for_principal(self.user)
            if record and record.createdTime:
                _dt = record.createdTime

        return datetime.utcfromtimestamp(_dt) if _dt else None


@component.adapter(ICourseInstanceEnrollmentRecord)
@interface.implementer(ILastSeenProvider)
def _course_enrollment_record_last_seen_time(record):
    user = User.get_user(record.Principal)
    course = record.CourseInstance
    return component.queryMultiAdapter((user, course), ILastSeenProvider)


@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def course_integration_collection(course, request):
    """
    Set the :class:`IIntegrationCollection` lineage as our course so
    that we can permission integration objects based on course permission.
    """
    if has_permission(ACT_CONTENT_EDIT, course, request):
        collection = IntegrationCollection(course)
        collection.__parent__ = course
        return collection

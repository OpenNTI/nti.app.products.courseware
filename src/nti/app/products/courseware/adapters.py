#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from pyramid import httpexceptions as hexc

from pyramid.interfaces import IRequest

from zope.annotation.interfaces import IAnnotations

from nti.app.authentication import get_remote_user

from nti.app.products.courseware import USER_ENROLLMENT_LAST_MODIFIED_KEY

from nti.app.products.courseware._outline_path import OutlinePathFactory

from nti.app.products.courseware.interfaces import ILegacyCommunityBasedCourseInstance
from nti.app.products.courseware.interfaces import ILegacyCourseConflatedContentPackageUsedAsCourse

from nti.appserver.context_providers import get_joinable_contexts
from nti.appserver.context_providers import get_top_level_contexts

from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import ForbiddenContextException
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ILibraryPathLastModifiedProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider
from nti.appserver.interfaces import ITrustedTopLevelContainerContextProvider

from nti.appserver.pyramid_authorization import is_readable

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import is_enrolled
from nti.contenttypes.courses.utils import get_enrollment_catalog
from nti.contenttypes.courses.utils import get_course_subinstances
from nti.contenttypes.courses.utils import is_course_instructor as is_instructor # BWC
from nti.contenttypes.courses.utils import content_unit_to_courses as indexed_content_unit_to_courses

from nti.contenttypes.presentation.interfaces import IPresentationAsset

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IHighlight

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

@component.adapter(ICourseOutline)
@interface.implementer(ICourseInstance)
def _outline_to_course(outline):
	result = find_interface(outline, ICourseInstance, strict=False)
	return result

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
		entry = package._v_global_legacy_catalog_entry
	except AttributeError:
		logger.warn("Consistency issue? No attribute on global package %s", package)
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

	result = indexed_content_unit_to_courses(unit,
											 include_sub_instances=include_sub_instances)
	return result

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit)
def _content_unit_to_course(unit):
	# get all courses, don't include sections
	courses = content_unit_to_courses(unit, False)
	# XXX: We probably need to check and see who's enrolled
	# to find the most specific course instance to return?
	# As it stands, we promise to return only a root course,
	# not a subinstance (section)
	# XXX: FIXME: This requires a one-to-one mapping
	return courses[0] if courses else None

def _is_user_enrolled(user, course):
	# Enrolled or instructor
	result = 	 user is not None \
			 and is_enrolled(course, user) or is_instructor(course, user)
	return result

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

def _get_top_level_contexts(obj):
	results = set()
	top_level_contexts = get_top_level_contexts(obj)
	for top_level_context in top_level_contexts:
		if 		ICourseInstance.providedBy(top_level_context) \
			or	ICourseCatalogEntry.providedBy(top_level_context):
			results.add(top_level_context)
	return results

def _is_catalog_entry_visible( entry ):
	return 		entry is not None \
			and not INonPublicCourseInstance.providedBy( entry ) \
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

	user = get_remote_user()
	courses = []
	catalog_entries = []
	for course_context in course_contexts:
		if ICourseCatalogEntry.providedBy(course_context):
			if _is_catalog_entry_visible( course_context ):
				catalog_entries.append(course_context)
		elif 	not _is_user_enrolled(user, course_context) \
			and not has_permission(ACT_CONTENT_EDIT, course_context, user):
			# Not enrolled and not an editor, get catalog entry.
			catalog_entry = ICourseCatalogEntry(course_context, None)
			# We only want to add publicly available entries.
			if _is_catalog_entry_visible( catalog_entry ):
				catalog_entries.append(catalog_entry)
		else:
			courses.append(course_context)

	# If we only have catalog entries, we should raise.
	# Otherwise, make sure our courses are returned first.
	if not courses and catalog_entries:
		raise ForbiddenContextException(catalog_entries)

	return courses + catalog_entries

@interface.implementer(IJoinableContextProvider)
@component.adapter(interface.Interface)
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
		raise hexc.HTTPUnprocessableEntity('Unexpected object %s' % type(obj))
	return target_ntiid

@interface.implementer(IHierarchicalContextProvider)
@component.adapter(ICourseInstance, interface.Interface)
def _hierarchy_from_obj_and_course(course, obj):
	target_ntiid = _get_target_ntiid(obj)
	# Typically, we get a user enrolled course here, but validate.
	context_courses = _get_valid_course_context(course)
	results = []
	if context_courses:
		course = context_courses[0]
		results = OutlinePathFactory(course, target_ntiid)()
		results = (results,) if results else results
	return results

def _get_courses_from_container(obj, user=None):
	results = set()
	if ICourseInstance.providedBy( obj ):
		results.add( obj )
		return results

	catalog = get_library_catalog()
	if catalog:
		containers = catalog.get_containers(obj)
		for container in containers:
			course = None

			container = find_object_with_ntiid(container)
			if user is not None:
				course = component.queryMultiAdapter((container, user), ICourseInstance)
			if course is None:
				course = ICourseInstance(container, None)

			if course is not None:
				results.add(course)
	if not results:
		courses = content_unit_to_courses(obj, include_sub_instances=True)
		results.update(courses)
	return results

@component.adapter(IHighlight, IUser)
@component.adapter(IContentUnit, IUser)
@component.adapter(IPresentationAsset, IUser)
@interface.implementer(IHierarchicalContextProvider)
def _hierarchy_from_obj_and_user(obj, user):
	container_courses = _get_courses_from_container(obj, user)
	possible_courses = _get_valid_course_context(container_courses)
	target_ntiid = _get_target_ntiid(obj)
	results = []
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
				if nodes and len(nodes) > 1:
					results.append(nodes)

	if not results:
		if caught_exception is not None:
			# No path found and this exception indicates the path goes through
			# an unpublished object. This case is unlikely.
			raise caught_exception

		# This is an edge case.  We have courses and catalog entries,
		# but our target NTIID only exists in a catalog entry that
		# may or may not be open. If we can't find our ntiid in our
		# course outlines, assume we don't have access and raise.
		# XXX: Not sure this is a good assumption.
		if container_courses and catalog_entries:
			raise ForbiddenContextException(catalog_entries)

		# No outline nodes, but we did have courses.
		results = [ (x,) for x in possible_courses ]
	return results

def _get_preferred_course(found_course):
	"""
	Prefer any enrolled subinstances to a board object found
	at a top-level course instance.
	"""
	# TODO: Do we need to do anything different for instructors?
	user = get_remote_user()
	if ICourseSubInstance.providedBy(found_course) or user is None:
		return found_course

	enrolled_courses = []
	catalog = get_enrollment_catalog()
	intids = component.getUtility(IIntIds)
	site_names = get_component_hierarchy_names()
	query = {
		IX_SITE:{'any_of': site_names},
		IX_USERNAME:{'any_of':(user.username,)}
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
	for course in courses:
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
def _courses_from_forum_obj_and_user(obj, *args, **kwargs):
	return _find_lineage_course(obj)

@component.adapter(IPost)
@component.adapter(ITopic)
@component.adapter(IForum)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_forum_obj(obj):
	return _find_lineage_course(obj, trusted=True)

@component.adapter(IContentUnit)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _courses_from_package(obj):
	# We could use the container index.
	courses = content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
	return results

@component.adapter(IContentUnit)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_package(obj):
	courses = content_unit_to_courses(obj, include_sub_instances=True)
	results = _catalog_entries_from_courses(courses)
	return results

@component.adapter(IContentUnit, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_package_and_user(obj, user):
	courses = content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
	return results

@component.adapter(ICourseInstance, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _top_level_context_from_course_and_user(obj, user):
	results = _get_valid_course_context(obj)
	return results

@component.adapter(ICourseInstance)
@interface.implementer(ITopLevelContainerContextProvider)
def _top_level_context_from_course(obj):
	results = _get_valid_course_context(obj)
	return results

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
	results = _catalog_entries_from_courses(courses)
	return results

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

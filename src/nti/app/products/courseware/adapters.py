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

from zope.intid import IIntIds

from pyramid import httpexceptions as hexc

from nti.app.authentication import get_remote_user

from nti.appserver.interfaces import ForbiddenContextException
from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider
from nti.appserver.interfaces import ILibraryPathLastModifiedProvider

from nti.appserver.pyramid_authorization import is_readable

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.contentlibrary.indexed_data import get_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IContentCourseInstance
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IHighlight
from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

from .interfaces import ILegacyCommunityBasedCourseInstance
from .interfaces import ILegacyCourseConflatedContentPackageUsedAsCourse

@interface.implementer(IContentPackageBundle)
@component.adapter(ILegacyCommunityBasedCourseInstance)
def _legacy_course_to_content_package_bundle(course):
	return course.ContentPackageBundle

@interface.implementer(IContentPackageBundle)
@component.adapter(IContentCourseInstance)
def _course_content_to_package_bundle(course):
	return course.ContentPackageBundle

@interface.implementer(IContentPackageBundle)
@component.adapter(ICourseCatalogEntry)
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
	cache_name = '_v_course_content_package_to_course'
	course_intid = getattr(package, cache_name, cache_name)
	course = None
	intids = component.getUtility(IIntIds)

	if course_intid is not cache_name:
		course = intids.queryObject(course_intid)

	if course is not None:
		return course

	# We go via the defined adapter from the catalog entry,
	# which we should have directly cached
	try:
		entry = package._v_global_legacy_catalog_entry
	except AttributeError:
		logger.warn("Consistency issue? No attribute on global package %s",
					package)
		entry = None

	course = ICourseInstance(entry, None)
	course_intid = intids.queryId(course, None)

	setattr(package, cache_name, course_intid)
	return course

def _content_unit_to_courses(unit, include_sub_instances=True):
	# XXX JAM These heuristics aren't well tested.

	# First, try the true legacy case. This involves
	# a direct mapping between courses and a catalog entry. It may be
	# slightly more reliable, but only works for true legacy cases.
	package = find_interface(unit, ILegacyCourseConflatedContentPackageUsedAsCourse,
							 strict=False)
	if package is not None:
		result = ICourseInstance(package, None)
		if result is not None:
			return (result,)

	# Nothing true legacy. find all courses that match this pacakge
	result = []
	package = find_interface(unit, IContentPackage, strict=False)
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog.iterCatalogEntries():
		instance = ICourseInstance(entry, None)
		if instance is None:
			continue
		if not include_sub_instances and ICourseSubInstance.providedBy(instance):
			continue
		try:
			packages = instance.ContentPackageBundle.ContentPackages
		except AttributeError:
			packages = (instance.legacy_content_package,)

		if package in packages:
			result.append(instance)
	return result

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit)
def _content_unit_to_course(unit):
	# get all courses, don't include sections
	courses = _content_unit_to_courses(unit, False)
	# XXX: We probably need to check and see who's enrolled
	# to find the most specific course instance to return?
	# As it stands, we promise to return only a root course,
	# not a subinstance (section)
	# XXX: FIXME: This requires a one-to-one mapping
	return courses[0] if courses else None

from .utils import is_course_instructor as is_instructor  # BWC

def _is_user_enrolled(user, course):
	# Enrolled or instructor
	if user is None:
		return False

	enrollments = ICourseEnrollments(course)
	record = enrollments.get_enrollment_for_principal(user)
	return 	record is not None \
		 or is_instructor(course, user)

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit, IUser)
def _content_unit_and_user_to_course(unit, user):
	# # get all courses
	courses = _content_unit_to_courses(unit, True)
	for instance in courses or ():
		if _is_user_enrolled(user, instance):
			return instance

	# nothing found return first course
	return courses[0] if courses else None

def _get_top_level_contexts(obj):
	results = set()
	for top_level_contexts in component.subscribers((obj,),
													ITopLevelContainerContextProvider):
		for top_level_context in top_level_contexts:
			if 		ICourseInstance.providedBy(top_level_context) \
				or	ICourseCatalogEntry.providedBy(top_level_context):
				results.add(top_level_context)
	return results

def _get_valid_course_context(course_contexts):
	"""
	Validate course context access for remote_user, returning
	catalog entries otherwise.
	"""
	if not course_contexts:
		return ()

	if 		ICourseCatalogEntry.providedBy(course_contexts) \
		or 	ICourseInstance.providedBy(course_contexts):
		course_contexts = (course_contexts,)

	user = get_remote_user()
	results = []
	for course_context in course_contexts:
		if ICourseCatalogEntry.providedBy(course_context):
			if is_readable(course_context):
				results.append(course_context)
		elif not _is_user_enrolled(user, course_context):
			catalog_entry = ICourseCatalogEntry(course_context, None)
			# We only want to add publicly available entries.
			if catalog_entry is not None and is_readable(catalog_entry):
				results.append(catalog_entry)
		else:
			results.append(course_context)

	# If we only have catalog entries, we should raise.
	# Otherwise, make sure our courses are returned first.
	courses = []
	catalog_entries = []
	for context in results:
		if ICourseInstance.providedBy( context ):
			courses.append( context )
		else:
			catalog_entries.append( context )
	if not courses and catalog_entries:
		raise ForbiddenContextException( results )

	return courses + catalog_entries

@interface.implementer(IJoinableContextProvider)
@component.adapter(interface.Interface)
def _catalog_entry_from_container_object(obj):
	"""
	Using the container index, look for catalog entries that contain
	the given object.
	"""
	results = set()
	try:
		_get_top_level_contexts(obj)
	except ForbiddenContextException as e:
		results = set( e.joinable_contexts )
	return results

def _get_outline_target_objs( target_ntiid ):
	target_obj = find_object_with_ntiid(target_ntiid)
	if INTISlide.providedBy( target_obj ):
		try:
			# If we have slides embedded in videos, we need to
			# use the root NTIVideo to find our outline.
			slide_vid = find_object_with_ntiid( target_obj.slidevideoid )
			video_obj = find_object_with_ntiid( slide_vid.video_ntiid )
			if video_obj is not None:
				target_obj = video_obj
				target_ntiid = video_obj.ntiid
		except AttributeError:
			pass
	return target_ntiid, target_obj

def _get_outline_nodes(course, target_ntiid):
	"""
	For a course and target ntiid, look for the outline hierarchy
	used to get to the target ntiid.
	"""
	# Make sure we're permissioned on course
	course_contexts = _get_valid_course_context(course)
	if not course_contexts:
		return
	course_context = course_contexts[0]

	# This does not work with legacy courses.
	if not target_ntiid or getattr(course, 'Outline', None) is None:
		return (course_context,)

	# Get the containers for our object.
	catalog = get_catalog()
	target_ntiid, target_obj = _get_outline_target_objs( target_ntiid )
	containers = set(catalog.get_containers(target_obj)) if catalog else set()

	def _found_target(item):
		target_ntiid_ref = getattr(item, 'target_ntiid', None)
		ntiid_ref = getattr(item, 'ntiid', None)
		target_ref = getattr(item, 'target', None)
		ntiid_vals = set([target_ntiid_ref, ntiid_ref, target_ref])
		# We found our object's container, or we are the container.
		result = 	containers.intersection(ntiid_vals) \
				or 	target_ntiid in ntiid_vals

		if not result and target_ref:
			# We could have an item contained by our target item
			target_obj = find_object_with_ntiid(target_ref)
			if target_obj is not None:
				item_containers = catalog.get_containers(target_obj) if catalog else set()
				result = target_ntiid in item_containers

				if not result:
					# Legacy, perhaps our item is a page ref.
					try:
						target_children = [x.ntiid for x in target_obj.children]
						result = target_ntiid in target_children \
							or target_ntiid in target_obj.embeddedContainerNTIIDs
					except AttributeError:
						pass
		return result

	outline = course.Outline
	for outline_node in outline.values():
		for outline_content_node in outline_node.values():
			if outline_content_node.ContentNTIID == target_ntiid:
				return (course, outline_content_node)
			lesson_ntiid = getattr(outline_content_node, 'LessonOverviewNTIID', None)
			if not lesson_ntiid:
				continue
			lesson_overview = component.queryUtility(INTILessonOverview, name=lesson_ntiid)
			if lesson_overview is None:
				continue

			for overview_group in lesson_overview.items:
				for item in overview_group.items:
					if _found_target(item):
						# Return our course, leaf outline node, and overview.
						return (course_context, outline_content_node, item)
	return (course_context,)

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
	return _get_outline_nodes(course, target_ntiid)

def _get_courses_from_container(obj, user=None):
	catalog = get_catalog()
	results = set()
	if catalog:
		containers = catalog.get_containers(obj)
		for container in containers:
			container = find_object_with_ntiid(container)
			if user is not None:
				course = component.queryMultiAdapter((container, user), ICourseInstance)
			else:
				course = ICourseInstance(container, None)
			if course is not None:
				results.add(course)
	if not results:
		courses = _content_unit_to_courses(obj, include_sub_instances=True)
		results.update(courses)
	return results

@interface.implementer(IHierarchicalContextProvider)
@component.adapter(IHighlight, IUser)
@component.adapter(IContentUnit, IUser)
@component.adapter(IPresentationAsset, IUser)
def _hierarchy_from_obj_and_user(obj, user):
	container_courses = _get_courses_from_container(obj, user)
	container_courses = _get_valid_course_context(container_courses)
	target_ntiid = _get_target_ntiid(obj)
	results = [_get_outline_nodes(course, target_ntiid) \
				for course in container_courses]
	results = [x for x in results if x is not None]
	return results

def _get_preferred_course(found_course):
	"""
	Prefer any enrolled subinstances to a board object found
	at a top-level course instance.
	"""
	# TODO Do we need to do anything different for instructors?
	user = get_remote_user()
	if ICourseSubInstance.providedBy(found_course) or user is None:
		return found_course

	enrolled_courses = []
	for enrollments in component.subscribers((user,), IPrincipalEnrollments):
		for record in enrollments.iter_enrollments():
			course = ICourseInstance(record, None)
			if course is not None:
				enrolled_courses.append(course)

	if found_course not in enrolled_courses:
		for subinstance in found_course.SubInstances.values():
			if subinstance in enrolled_courses:
				return subinstance
	return found_course

def _find_lineage_course(obj):
	course = find_interface(obj, ICourseInstance, strict=False)
	if course is not None:
		course = _get_preferred_course(course)
		results = _get_valid_course_context(course)
		return results

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IPost)
@component.adapter(ITopic)
@component.adapter(IForum)
def _courses_from_forum_obj(obj):
	return _find_lineage_course(obj)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IPost, IUser)
@component.adapter(ITopic, IUser)
@component.adapter(IForum, IUser)
def _courses_from_forum_obj_and_user(obj, _):
	return _find_lineage_course(obj)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IContentUnit)
def _courses_from_package(obj):
	# We could use the container index.
	courses = _content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
	return results

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IContentUnit, IUser)
def _courses_from_package_and_user(obj, user):
	courses = _content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
	return results

def __courses_from_obj_and_user(obj, user=None):
	# TODO We need to index content units so this works for more
	# contained objects.
	container_courses = _get_courses_from_container(obj, user)
	if not container_courses:
		# No? Are we contained?
		container_id = getattr(obj, 'containerId', None)
		container_obj = find_object_with_ntiid(container_id) if container_id else None
		if container_obj is not None:
			container_courses = _get_courses_from_container(container_obj, user)
	results = _get_valid_course_context(container_courses)
	return results

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IHighlight, IUser)
@component.adapter(IPresentationAsset, IUser)
def _courses_from_obj_and_user(obj, user):
	return __courses_from_obj_and_user(obj, user)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IHighlight)
@component.adapter(IPresentationAsset)
def _courses_from_obj(obj):
	return __courses_from_obj_and_user(obj)

@interface.implementer(ILibraryPathLastModifiedProvider)
@component.adapter(IUser)
def _enrollment_last_modified( user ):
	result = 0
	# Could use index here.
	for enrollments in component.subscribers((user,), IPrincipalEnrollments):
			for record in enrollments.iter_enrollments():
				enroll_last_mod = getattr( record, 'lastModified', 0 )
				result = max( result, enroll_last_mod )
	return result

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

from zope.annotation.interfaces import IAnnotations

from nti.app.authentication import get_remote_user

from nti.appserver.context_providers import get_top_level_contexts
from nti.appserver.context_providers import get_joinable_contexts

from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import ForbiddenContextException
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ILibraryPathLastModifiedProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider

from nti.appserver.interfaces import ITrustedTopLevelContainerContextProvider

from nti.appserver.pyramid_authorization import is_readable

from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IContentPackageBundle

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import IContentCourseInstance

from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import IPresentationAsset
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IHighlight
from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic
from nti.dataserver.contenttypes.forums.interfaces import IForum

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

from .interfaces import ILegacyCommunityBasedCourseInstance
from .interfaces import ILegacyCourseConflatedContentPackageUsedAsCourse

from . import USER_ENROLLMENT_LAST_MODIFIED_KEY

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
		logger.warn("Consistency issue? No attribute on global package %s", package)
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

from nti.contenttypes.courses.utils import is_course_instructor as is_instructor  # BWC

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
	top_level_contexts = get_top_level_contexts(obj)
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

	if ICourseInstance.providedBy(course_contexts):
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
		if ICourseInstance.providedBy(context):
			courses.append(context)
		else:
			catalog_entries.append(context)
	if not courses and catalog_entries:
		raise ForbiddenContextException(results)

	return courses + catalog_entries

@interface.implementer(IJoinableContextProvider)
@component.adapter(interface.Interface)
def _catalog_entry_from_container_object(obj):
	return get_joinable_contexts(obj)

class _OutlinePathFactory(object):

	def __init__(self, course_context, target_ntiid):
		self.original_target_ntiid = target_ntiid
		self.target_ntiid, self.target_obj = self._get_outline_target_objs(target_ntiid)
		self.course_context = course_context

	def _get_outline_target_objs(self, target_ntiid):
		"""
		Returns the target ntiid/obj to search for in outline.
		"""
		target_obj = find_object_with_ntiid(target_ntiid)

		# For slide objects, the video itself only shows up
		# in the outline hierarchy.
		if 		INTISlide.providedBy(target_obj) \
			or 	INTISlideDeck.providedBy(target_obj) \
			or	INTISlideVideo.providedBy(target_obj):

			try:
				if INTISlideDeck.providedBy(target_obj):
					# Arbitrary?
					slide_vid = target_obj.videos[0]
				elif INTISlide.providedBy(target_obj):
					slide_vid = find_object_with_ntiid(target_obj.slidevideoid)
				else:
					slide_vid = target_obj

				# If we have slides embedded in videos, we need to
				# use the root NTIVideo to find our outline.
				video_obj = find_object_with_ntiid(slide_vid.video_ntiid)
				if video_obj is not None:
					target_obj = video_obj
					target_ntiid = video_obj.ntiid
			except (AttributeError, IndexError):
				pass
		return target_ntiid, target_obj

	@property
	def catalog(self):
		return get_library_catalog()

	@property
	def target_obj_containers(self):
		# Get the containers for our object.
		containers = set(self.catalog.get_containers(self.target_obj)) if self.catalog else set()
		return containers

	def _get_slidedeck_for_video(self, video_ntiid, lesson_overview):
		"""
		For a video ntiid, return the slide deck containing it,
		if it is a video on a slide deck.
		"""
		try:
			content_ntiid = lesson_overview.__parent__.ContentNTIID
		except AttributeError:
			return
		for slide_deck in self.catalog.search_objects(
										container_ntiids=content_ntiid,
										provided=INTISlideDeck,
										sites=get_component_hierarchy_names()):
			for slide_video in slide_deck.videos:
				if slide_video.video_ntiid == video_ntiid:
					return slide_deck
		return None

	def _get_outline_result_items(self, item, lesson_overview):
		"""
		Returns the outline endpoints.  For slides/decks we want to return
		those instead of video they live on. For slide videos, we want the
		slidedeck to be returned.
		"""
		original_obj = find_object_with_ntiid(self.target_ntiid)
		if 		INTISlide.providedBy(original_obj) \
			or 	INTISlideVideo.providedBy(original_obj):

			deck = find_object_with_ntiid(original_obj.slidedeckid)
			results = (deck, original_obj,)
		elif INTISlideDeck.providedBy(original_obj):
			results = (original_obj,)
		elif INTIVideo.providedBy(original_obj):
			slide_deck = self._get_slidedeck_for_video(self.original_target_ntiid,
													lesson_overview)
			if slide_deck is not None:
				results = (slide_deck, item,)
			else:
				results = (item,)
		else:
			results = (item,)
		return results

	def _overview_item_contains_target(self, item, check_contained=True):
		"""
		Check if the overview item contains our target object. The simple case
		is we are looking for an ntiid that is our item.

		`check_contained` checks to see if the given item is contained by
		our target object.

		Example cases:
			* Content unit page containing videos. We do not want to return the
			video object since we are looking for the related work ref (not check-contained).
			* Content unit page contained by a related work ref (need check-contained).
			* Video contained by an related work ref (need check-contained).
		"""
		target_ntiid_ref = getattr(item, 'target_ntiid', None)
		ntiid_ref = getattr(item, 'ntiid', None)
		target_ref = getattr(item, 'target', None)
		ntiid_vals = set([target_ntiid_ref, ntiid_ref, target_ref])
		# We found our object's container, or we are the container.
		result = 	self.target_obj_containers.intersection(ntiid_vals) \
				or 	self.target_ntiid in ntiid_vals

		if 		not result \
			and target_ref \
			and check_contained:
			# We could have an item contained by our target item
			target_ref_obj = find_object_with_ntiid(target_ref)
			if target_ref_obj is not None:
				item_containers = self.catalog.get_containers(target_ref_obj) if self.catalog else set()
				result = self.target_ntiid in item_containers

				if not result:
					# Legacy, perhaps our item is a page ref.
					try:
						target_children = [x.ntiid for x in target_ref_obj.children]
						result = self.target_ntiid in target_children \
							or self.target_ntiid in target_ref_obj.embeddedContainerNTIIDs
					except AttributeError:
						pass
		return result

	def _lesson_overview_contains_target(self, outline_content_node, lesson_overview):
		def _do_check(check_contained=True):
			for overview_group in lesson_overview.items or ():
				for item in overview_group.items or ():
					if self._overview_item_contains_target(item, check_contained):
						endpoints = self._get_outline_result_items(item, lesson_overview)
						# Return our course, leaf outline node, and overview.
						results = [self.course_context, outline_content_node]
						results.extend(endpoints)
						return results

		results = None
		if IContentUnit.providedBy(self.target_obj):
			# First check if our content unit is a related work ref.
			# We don't want to return a video that may be contained
			# by our target content unit when we are looking for just
			# a related work ref.
			results = _do_check(False)
		if not results:
			results = _do_check()
		return results


	def __call__(self):
		"""
		For a course and target ntiid, look for the outline hierarchy
		used to get to the target ntiid.  We assume the
		course we have here is permissioned.
		"""
		if self.course_context is None:
			return

		# This does not work with legacy courses.
		if 		not self.target_ntiid \
			or 	getattr(self.course_context, 'Outline', None) is None:
			return (self.course_context,)

		outline = self.course_context.Outline
		for outline_node in outline.values():
			for outline_content_node in outline_node.values():
				if getattr( outline_content_node, 'ContentNTIID', None ) == self.target_ntiid:
					return (self.course_context, outline_content_node)
				lesson_ntiid = getattr(outline_content_node, 'LessonOverviewNTIID', None)
				if not lesson_ntiid:
					continue
				lesson_overview = component.queryUtility(INTILessonOverview,
														name=lesson_ntiid)
				if lesson_overview is None:
					continue

				results = self._lesson_overview_contains_target(outline_content_node,
																lesson_overview)
				if results is not None:
					return results
		return (self.course_context,)

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
	course = _get_valid_course_context(course)[0]
	return _OutlinePathFactory(course, target_ntiid)()

def _get_courses_from_container(obj, user=None):
	results = set()
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
		courses = _content_unit_to_courses(obj, include_sub_instances=True)
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
	for course in possible_courses:
		if ICourseCatalogEntry.providedBy(course):
			catalog_entries.add(course)
		else:
			nodes = _OutlinePathFactory(course, target_ntiid)()
			if nodes and len(nodes) > 1:
				results.append(nodes)

	# This is an edge case.  We have courses and catalog entries,
	# but our target NTIID only exists in a catalog entry that
	# may or may not be open. If we can't find our ntiid in our
	# course outlines, assume we don't have access and raise.
	if container_courses and catalog_entries and not results:
		raise ForbiddenContextException(catalog_entries)
	# No outline nodes, but we did have courses.
	if not results:
		results = [ (x,) for x in possible_courses ]
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
	# TODO: Enrollment index
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
	courses = _content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
	return results

@component.adapter(IContentUnit)
@interface.implementer(ITrustedTopLevelContainerContextProvider)
def _catalog_entries_from_package(obj):
	courses = _content_unit_to_courses(obj, include_sub_instances=True)
	results = _catalog_entries_from_courses(courses)
	return results

@component.adapter(IContentUnit, IUser)
@interface.implementer(ITopLevelContainerContextProvider)
def _courses_from_package_and_user(obj, user):
	courses = _content_unit_to_courses(obj, include_sub_instances=True)
	results = _get_valid_course_context(courses)
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

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import zope.intid
from zope import interface
from zope import component

from pyramid import httpexceptions as hexc

from nti.appserver.interfaces import IJoinableContextProvider
from nti.appserver.interfaces import IHierarchicalContextProvider
from nti.appserver.interfaces import ITopLevelContainerContextProvider

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

from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver.interfaces import IUser

from nti.dataserver.contenttypes.forums.interfaces import IPost
from nti.dataserver.contenttypes.forums.interfaces import ITopic

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
	intids = component.getUtility(zope.intid.IIntIds)

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
	package = find_interface(unit, ILegacyCourseConflatedContentPackageUsedAsCourse, strict=False)
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

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit, IUser)
def _content_unit_and_user_to_course(unit, user):
	# # get all courses
	courses = _content_unit_to_courses(unit, True)
	for instance in courses or ():
		# check enrollment
		enrollments = ICourseEnrollments(instance)
		record = enrollments.get_enrollment_for_principal(user)
		if record is not None:
			return instance

		# check role
		if is_instructor(instance, user):
			return instance

	# nothing found return first course
	return courses[0] if courses else None

def _get_top_level_contexts( obj ):
	results = set()
	for top_level_contexts in component.subscribers( (obj,),
													ITopLevelContainerContextProvider ):
		for top_level_context in top_level_contexts:
			if ICourseInstance.providedBy( top_level_context ):
				results.add( top_level_context )
	return results

@interface.implementer(IJoinableContextProvider)
@component.adapter(interface.Interface)
def _catalog_entry_from_container_object(obj):
	"""
	Using the container index, look for catalog entries that contain
	the given object.
	"""
	results = set()
	courses = _get_top_level_contexts( obj )
	for course in courses or ():
		catalog_entry = ICourseCatalogEntry(course, None)

		# We only want to add publicly available entries.
		if catalog_entry is not None and is_readable(catalog_entry):
			results.add(catalog_entry)
	return results

def _get_outline_nodes( course, target_ntiid ):
	"""
	For a course and target ntiid, look for the outline hierarchy
	used to get to the target ntiid.
	"""
	# This does not work with legacy courses.
	if not target_ntiid or getattr( course, 'Outline', None ) is None:
		return (course,)

	# Get the containers for our object.
	catalog = get_catalog()
	target_obj = find_object_with_ntiid( target_ntiid )
	containers = set( catalog.get_containers( target_obj ) ) if catalog else set()

	def _found_target( item ):
		target_ntiid_ref = getattr( item, 'target_ntiid', None )
		ntiid_ref = getattr( item, 'ntiid', None )
		target_ref = getattr( item, 'target', None )
		ntiid_vals = set( [target_ntiid_ref, ntiid_ref, target_ref] )
		result = containers.intersection( ntiid_vals )
		if not result and target_ref:
			# Legacy, perhaps our item is a page ref.
			target_obj = find_object_with_ntiid( target_ref )
			if target_obj is not None:
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
			lesson_ntiid = getattr( outline_content_node, 'LessonOverviewNTIID', None )
			if not lesson_ntiid:
				continue
			lesson_overview = component.queryUtility( INTILessonOverview, name=lesson_ntiid )
			for overview_group in lesson_overview.items:
				for item in overview_group.items:
					if _found_target( item ):
						# Return our course, leaf outline node, and overview.
						return (course, outline_content_node, item)
	return (course,)

def _get_target_ntiid( obj ):
	target_ntiid = getattr( obj, 'ntiid', None )
	# Content cards are pseudo objects, so get
	# the nearest available ntiid.
	if not target_ntiid:
		try:
			target_ntiid = obj.path[-1].ntiid
		except AttributeError:
			pass
	if not target_ntiid:
		raise hexc.HTTPUnprocessableEntity( 'Unexpected object %s' % type( obj ) )
	return target_ntiid

@interface.implementer(IHierarchicalContextProvider)
@component.adapter( ICourseInstance, interface.Interface )
def _hierarchy_from_obj_and_course( course, obj ):
	target_ntiid = _get_target_ntiid( obj )
	return _get_outline_nodes(course, target_ntiid)

def _get_courses_from_container( obj, user=None ):
	catalog = get_catalog()
	results = set()
	if catalog:
		containers = catalog.get_containers(obj)
		for container in containers:
			container = find_object_with_ntiid(container)
			if user is not None:
				course = component.queryMultiAdapter( (container,user), ICourseInstance )
			else:
				course = ICourseInstance(container, None)
			if course is not None:
				results.add(course)
	return results

@interface.implementer(IHierarchicalContextProvider)
@component.adapter(interface.Interface, IUser)
def _hierarchy_from_obj_and_user(obj, user):
	container_courses = _get_courses_from_container( obj, user )
	target_ntiid = _get_target_ntiid( obj )
	results = [_get_outline_nodes(course, target_ntiid) \
				for course in container_courses]
	return results

def _find_lineage_course( obj ):
	course = find_interface(obj, ICourseInstance, strict=False)
	if course is not None:
		return (course,)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IPost)
@component.adapter(ITopic)
def _courses_from_forum_obj(obj):
	return _find_lineage_course( obj )

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(IPost, IUser)
@component.adapter(ITopic, IUser)
def _courses_from_forum_obj_and_user(obj, _):
	return _find_lineage_course( obj )

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter( IContentUnit )
def _courses_from_package(obj):
	# We could tweak the adapter above to return
	# all possible courses, or use the container index.
	course = ICourseInstance(obj, None)
	if course:
		return (course,)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter( IContentUnit, IUser )
def _courses_from_package_and_user(obj, user):
	course = component.queryMultiAdapter( (obj,user), ICourseInstance )
	if course:
		return (course,)

def __courses_from_obj_and_user(obj, user=None):
	# TODO We need to index content units so this works for more
	# contained objects.
	container_courses = _get_courses_from_container( obj, user )
	if not container_courses:
		# No? Are we contained?
		container_id = getattr( obj, 'containerId', None )
		container_obj = find_object_with_ntiid( container_id ) if container_id else None
		if container_obj is not None:
			container_courses = _get_courses_from_container( container_obj, user )
	return container_courses

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(interface.Interface, IUser)
def _courses_from_obj_and_user(obj, user):
	__courses_from_obj_and_user(obj, user)

@interface.implementer(ITopLevelContainerContextProvider)
@component.adapter(interface.Interface)
def _courses_from_obj(obj):
	__courses_from_obj_and_user(obj)

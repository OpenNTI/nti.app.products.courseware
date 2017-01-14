#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.threadlocal import get_current_request

from nti.appserver.interfaces import ForbiddenContextException

from nti.appserver.pyramid_authorization import has_permission

from nti.contentlibrary.interfaces import IContentUnit

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.presentation.interfaces import INTISlide
from nti.contenttypes.presentation.interfaces import INTIVideo
from nti.contenttypes.presentation.interfaces import INTISlideDeck
from nti.contenttypes.presentation.interfaces import INTIMediaRoll
from nti.contenttypes.presentation.interfaces import IConcreteAsset
from nti.contenttypes.presentation.interfaces import INTISlideVideo
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.coremetadata.interfaces import IPublishable

from nti.dataserver import authorization as nauth

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.property.property import Lazy

from nti.site.site import get_component_hierarchy_names

class OutlinePathFactory(object):
	"""
	Given a course context and target ntiids, traverse the course
	outline finding a path to the target object.
	"""

	def __init__(self, course_context, target_ntiid):
		self.original_target_ntiid = target_ntiid
		self.target_ntiid, self.target_obj = self._get_outline_target_objs(target_ntiid)
		self.course_context = course_context

	@Lazy
	def request(self):
		return get_current_request()

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

	def _get_slidedeck_for_video(self, target_ntiid, lesson_overview):
		"""
		For a target ntiid, return the slide deck containing it,
		if it is a video on a slide deck.
		"""
		try:
			content_ntiid = lesson_overview.__parent__.ContentNTIID
		except AttributeError:
			return

		def _check_slidedeck(slide_deck):
			# We may have the slide deck or a contained video.
			if slide_deck.ntiid == target_ntiid:
				return True
			for slide_video in slide_deck.videos:
				if slide_video.video_ntiid == target_ntiid:
					return True
			return False

		for slide_deck in self.catalog.search_objects(
										container_ntiids=content_ntiid,
										provided=INTISlideDeck,
										sites=get_component_hierarchy_names()):
			if _check_slidedeck(slide_deck):
				return slide_deck
		return None

	def _convert_refs(self, objects):
		results = []
		for item in objects or ():
			# Should we do this for all asset refs?
			item = IConcreteAsset(item, item)
			results.append(item)
		return results

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
			# We want our slide deck, if applicable.
			slide_deck = self._get_slidedeck_for_video(self.original_target_ntiid,
													   lesson_overview)
			if slide_deck is not None:
				# Our item may be a media roll here too.
				results = (slide_deck, original_obj,)
			elif INTIMediaRoll.providedBy(item):
				# Currently, we only need to return the actual video object, and
				# not its media roll container.
				results = (original_obj,)
			else:
				results = (item,)
		else:
			results = (item,)
		# Make sure we don't return refs.
		results = self._convert_refs(results)
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
			* Video contained by a related work ref (need check-contained).
			* Video contained by a video roll.
			* Target obj is content unit page containing a self-assessment.
		"""
		item = IConcreteAsset(item, item)
		target_ntiid_ref = getattr(item, 'target_ntiid', None)
		ntiid_ref = getattr(item, 'ntiid', None)
		target_ref = getattr(item, 'target', None)
		# Some related work refs have hrefs pointing at content (instead of target).
		href = getattr(item, 'href', None)
		ntiid_vals = set([target_ntiid_ref, ntiid_ref, target_ref, href])

		# We found our object's container, or we are the container.
		result = 	self.target_obj_containers.intersection(ntiid_vals) \
				or 	self.target_ntiid in ntiid_vals

		# Ok, do we have a media roll.
		if not result and INTIMediaRoll.providedBy(item):
			for child in item.items or ():
				child_ntiid = getattr(child, 'ntiid', '')
				child_target = getattr(child, 'target', '')
				if self.target_ntiid in (child_ntiid, child_target):
					result = True
					break

		# Self assessment item contained by our target_obj.
		if not result:
			result = ntiid_ref in getattr(self.target_obj, 'embeddedContainerNTIIDs', ())

		if 		not result \
			and target_ref \
			and check_contained:
			# We could have an item contained by our target item
			target_ref_obj = find_object_with_ntiid(target_ref)
			if target_ref_obj is not None:
				item_containers = self.catalog.get_containers(target_ref_obj) if self.catalog else set()
				result = self.target_ntiid in item_containers \
					or self.target_ntiid == getattr( target_ref_obj, 'containerId', '' )

				if not result:
					# Legacy, perhaps our item is a page ref.
					try:
						target_children = [x.ntiid for x in target_ref_obj.children]
						result = 	self.target_ntiid in target_children \
								or 	self.target_ntiid in target_ref_obj.embeddedContainerNTIIDs
					except AttributeError:
						pass
		return result

	def _is_visible(self, item):
		"""
		Object is published or we're an editor.
		"""
		return 		not IPublishable.providedBy(item) \
				or 	item.is_published() \
				or	has_permission(nauth.ACT_CONTENT_EDIT, item, self.request)

	def _validate_path_visibility(self, path):
		"""
		Validate all of our path objects are accessible (published) by
		our user. Otherwise we'll return a 403.
		"""
		for item in path or ():
			if not self._is_visible(item):
				raise ForbiddenContextException()

	def _lesson_overview_contains_target(self, outline_content_node, lesson_overview):
		def _do_check(check_contained=True):
			for overview_group in lesson_overview.items or ():
				for item in overview_group.items or ():
					if self._overview_item_contains_target(item, check_contained):
						endpoints = self._get_outline_result_items(item, lesson_overview)
						# Return our course, leaf outline node, and overview.
						results = [self.course_context, outline_content_node]
						results.extend(endpoints)
						self._validate_path_visibility((outline_content_node, lesson_overview, endpoints))
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
		used to get to the target ntiid.  We assume the course we have
		here is permissioned.
		"""
		if self.course_context is None:
			return

		if 		not self.target_ntiid \
			or 	getattr(self.course_context, 'Outline', None) is None:
			return (self.course_context,)

		outline = self.course_context.Outline
		for outline_node in outline.values():
			for outline_content_node in outline_node.values():
				content_ntiid = getattr(outline_content_node, 'ContentNTIID', None)
				# I don't believe legacy courses have these lessons.
				# Navigate through lesson first.
				lesson_ntiid = outline_content_node.LessonOverviewNTIID
				lesson_overview = INTILessonOverview(outline_content_node, None)
				if lesson_overview is not None:
					if lesson_ntiid == self.target_ntiid:
						results = (self.course_context, outline_content_node, self.target_obj)
					else:
						results = self._lesson_overview_contains_target(outline_content_node,
																		lesson_overview)
					if results is not None:
						return results
				# Check if our content node points directly at the content.
				if content_ntiid == self.target_ntiid:
					# Our target_obj is probably an IContentUnit.
					return (self.course_context, outline_content_node)
				# Legacy courses; try looking in unit for contained item.
				if content_ntiid != lesson_ntiid:
					unit = find_object_with_ntiid(content_ntiid)
					if 		IContentUnit.providedBy(unit) \
						and self.target_ntiid in unit.embeddedContainerNTIIDs:
						return (self.course_context, outline_content_node, self.target_obj)
		return (self.course_context,)

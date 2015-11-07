#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
NTIID support.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import calendar

from zope import component
from zope import interface

from nti.app.authentication import get_remote_user

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance

from nti.dataserver.contenttypes.forums.ntiids import resolve_ntiid_in_board
from nti.dataserver.contenttypes.forums.ntiids import resolve_forum_ntiid_in_board

from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import escape_provider
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.ntiids.interfaces import INTIIDResolver

from .interfaces import NTIID_TYPE_COURSE_FORUM
from .interfaces import NTIID_TYPE_COURSE_TOPIC
from .interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC
from .interfaces import NTIID_TYPE_COURSE_SECTION_FORUM
from .interfaces import IPrincipalAdministrativeRoleCatalog

COURSE_NTIID_PREFIX = 'tag:nextthought.com,2011-10:NTI-CourseInfo-'

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_SECTION_TOPIC)
class _EnrolledCourseSectionTopicNTIIDResolver(object):

	def __init__(self):
		pass

	# Whether, when we find a match to a course, we return the sub
	# instance we're actually enrolled in or the parent instance
	# (the main course)
	allow_section_match = True

	def _sort_enrollments(self, enrollments):
		# returns a list of (course, catalog_entry) objects,
		# with any subinstances I'm enrolled in coming first
		# if section matches are allowed, otherwise those are
		# excluded. We also make sure the most recent things are first
		records = []
		for record in enrollments.iter_enrollments():
			try:
				course = ICourseInstance(record)
			except TypeError:
				# Never seen this, being proactive
				logger.warn("User enrolled %s in stale course",
							record)
				continue

			try:
				catalog_entry = ICourseCatalogEntry(course, None)
			except TypeError:
				# Seen this is alpha, possible due to the early content
				# shifting before enrollment cleanup was correct?
				# maybe it can go away
				logger.warn("User enrolled %r in course %r that no longer has CCE",
							record, course)
				continue

			if catalog_entry is not None:
				records.append((course, catalog_entry, record))

		# stable sort, the key will be the same for all the subinstances
		# and then all the parent
		def key(record):
			ts = 0
			# admin roles do not have created time, in that case
			if hasattr(record[2], 'createdTime'):
				ts = -record[2].createdTime
			if not ts and catalog_entry is not None:
				ts = -calendar.timegm(catalog_entry.StartDate.utctimetuple())
			result = (0 if ICourseSubInstance.providedBy(record[0]) else 1, ts)
			return result

		records.sort(key=key)
		return records

	def _escape_entry_provider(self, entry):
		result = escape_provider(entry.ProviderUniqueID) if entry is not None else None
		return result

	def _solve_for_iface(self, ntiid, iface, provider_name, user, catalog_entry_matches=None):

		def _catalog_entry_matches(catalog_entry, provider_name):
			return self._escape_entry_provider(catalog_entry) == provider_name

		catalog_entry_matches = catalog_entry_matches if catalog_entry_matches else _catalog_entry_matches

		def _get_ntiid_for_subinstance(ntiid, subinstance, main_course):
			result = None
			# First, check section if we do not force them to
			# use the parent.
			if 	self.allow_section_match or \
				INonPublicCourseInstance.providedBy(main_course):
				result = self._find_in_course(subinstance, ntiid)

			# Check main course if we need to.
			if result is None:
				result = self._find_in_course(main_course, ntiid)
			return result

		for enrollments in component.subscribers((user,), iface):
			for course, catalog_entry, _ in self._sort_enrollments(enrollments):
				# The webapp is passing the course context here as the provider_name.
				# This may be necessary to avoid topic name collisions; especially with
				# instructors enrolled in many sections.
				# Otherwise, the client will be passing the content specified
				# section.
				result = None
				if catalog_entry_matches(catalog_entry, provider_name):
					if ICourseSubInstance.providedBy(course):
						main_course = course.__parent__.__parent__
						main_cce = ICourseCatalogEntry(main_course, None)
						result = _get_ntiid_for_subinstance(ntiid, course, main_course)
					else:
						# The ntiid references a top-level course.
						result = self._find_in_course(course, ntiid)
				# No? Is it a subcourse? Check the main course to see if it matches.
				# If it does, we still want to return the most specific
				# discussions allowed (either our section or, if not allowed, the parent)
				if result is None and ICourseSubInstance.providedBy(course):
					main_course = course.__parent__.__parent__
					main_cce = ICourseCatalogEntry(main_course, None)
					if catalog_entry_matches(main_cce, provider_name):
						# Some legacy cases (CHEM_4970) may match provider names.
						result = _get_ntiid_for_subinstance(ntiid, course, main_course)

				if result is not None:
					return result
		return None

	def _do_resolve(self, ntiid, user, provider_name, catalog_entry_matches=None):
		result = self._solve_for_iface(ntiid, IPrincipalAdministrativeRoleCatalog,
										   provider_name, user,
										   catalog_entry_matches=catalog_entry_matches)

		# Enrolled
		if result is None:
			result = self._solve_for_iface(ntiid, IPrincipalEnrollments,
											provider_name, user,
											catalog_entry_matches=catalog_entry_matches)
		return result

	def resolve(self, ntiid):
		user = get_remote_user()
		if user is None:
			return

		provider_name = get_provider(ntiid)
		provider_name_ntiid = COURSE_NTIID_PREFIX + provider_name

		result = find_object_with_ntiid(provider_name_ntiid)
		if result is not None:
			# Ok we have a course, we should be able to definitively return based
			# on enrollments.
			def catalog_entry_matches(catalog_entry, _):
				return catalog_entry.ntiid == provider_name_ntiid
			result = self._do_resolve(ntiid, user, provider_name,
									catalog_entry_matches=catalog_entry_matches)
		else:
			# The legacy approach, which may collide across semesters.
			result = self._do_resolve(ntiid, user, provider_name)
		return result

	def _find_in_course(self, course, ntiid):
		result = resolve_ntiid_in_board(ntiid, course.Discussions)
		return result

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_TOPIC)
class _EnrolledCourseRootTopicNTIIDResolver(_EnrolledCourseSectionTopicNTIIDResolver):

	allow_section_match = False  # always the root

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_SECTION_FORUM)
class _EnrolledCourseSectionForumNTIIDResolver(_EnrolledCourseSectionTopicNTIIDResolver):

	def _find_in_course(self, course, ntiid):
		result = resolve_forum_ntiid_in_board(ntiid, course.Discussions)
		return result

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_FORUM)
class _EnrolledCourseRootForumNTIIDResolver(_EnrolledCourseSectionForumNTIIDResolver):

	allow_section_match = False  # always the root

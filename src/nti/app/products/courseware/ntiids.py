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

from zope import interface
from zope import component

from nti.ntiids.interfaces import INTIIDResolver
from .interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC
from .interfaces import NTIID_TYPE_COURSE_TOPIC
from .interfaces import IPrincipalAdministrativeRoleCatalog

from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.ntiids.ntiids import get_provider
from nti.ntiids.ntiids import escape_provider

from nti.app.authentication import get_remote_user

from nti.dataserver.contenttypes.forums.ntiids import resolve_ntiid_in_board

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_SECTION_TOPIC)
class _EnrolledCourseSectionTopicNTIIDResolver(object):

	def __init__(self):
		pass

	#: Whether, when we find a match to a course, we return the sub
	#: instance we're actually enrolled in or the parent instance
	#: (the main course)
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
				catalog_entry = ICourseCatalogEntry(course)
			except TypeError:
				# Seen this is alpha, possible due to the early content
				# shifting before enrollment cleanup was correct?
				# maybe it can go away
				logger.warn("User enrolled %r in course %r that no longer has CCE",
							record, course)
				continue

			records.append( (course, catalog_entry, record))

		# stable sort, the key will be the same for all the subinstances
		# and then all the parent
		def key(record):
			return (0 if ICourseSubInstance.providedBy(record[0]) else 1,
					# admin roles do not have created time, in that case
					getattr(record[2], 'createdTime', 0) or (-calendar.timegm(catalog_entry.StartDate.utctimetuple())
															 if catalog_entry is not None
															 else 0))
		records.sort( key=key )

		return records

	def resolve(self, ntiid):
		user = get_remote_user()
		if user is None:
			return

		provider_name = get_provider(ntiid)

		for iface in IPrincipalEnrollments, IPrincipalAdministrativeRoleCatalog:
			for enrollments in component.subscribers((user,), iface):
				for course, catalog_entry, _ in self._sort_enrollments(enrollments):
					if escape_provider(catalog_entry.ProviderUniqueID) == provider_name:
						return self._find_in_course(course, ntiid)

					# No? Is it a subcourse? Check the main course to see if it matches.
					# If it does, we still want to return the most specific
					# discussions allowed (either our section or, if not allowed, the parent)
					if ICourseSubInstance.providedBy(course):
						main_course = course.__parent__.__parent__
						main_cce = ICourseCatalogEntry(main_course, None)
						if main_cce and escape_provider(main_cce.ProviderUniqueID) == provider_name:
							most_specific_course = course if self.allow_section_match else main_course
							return self._find_in_course(most_specific_course, ntiid)

	def _find_in_course(self, course, ntiid):
		return resolve_ntiid_in_board(ntiid, course.Discussions)

@interface.implementer(INTIIDResolver)
@interface.named(NTIID_TYPE_COURSE_TOPIC)
class _EnrolledCourseRootTopicNTIIDResolver(_EnrolledCourseSectionTopicNTIIDResolver):

	allow_section_match = False # always the root

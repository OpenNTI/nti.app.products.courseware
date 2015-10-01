#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.copypastemove.interfaces import IObjectMover

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.contenttypes.courses.enrollment import SectionSeat
from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

def migrate(ntiid, scope=ES_PUBLIC, max_seat_count=25, sections=(),
			dry_run=False, verbose=False):

	context = find_object_with_ntiid(ntiid)
	instance = ICourseInstance(context, None)
	if instance is None:
		catalog = component.getUtility(ICourseCatalog)
		try:
			context = catalog.getCatalogEntry(ntiid)
			instance = ICourseInstance(context, None)
		except KeyError:
			pass
	if instance is None:
		raise ValueError("Course cannot be found")

	parent = course = instance
	if ICourseSubInstance.providedBy(course):
		parent = course.__parent__.__parent__

	if not sections:
		sections = list(parent.SubInstances.keys())

	items = []
	for section in sections:
		if section not in parent.SubInstances:
			raise KeyError("Invalid section", section)
		sub_instance = parent.SubInstances[section]
		count = ICourseEnrollments(sub_instance).count_enrollments()
		items.append(SectionSeat(section, count))

	items.sort()
	source_enrollments = IDefaultCourseInstanceEnrollmentStorage(course)

	count = 0
	log = logger.warn if not verbose else logger.info

	for source_prin_id in list(source_enrollments):

		if not source_prin_id or User.get_user(source_prin_id) is None:
			# dup enrollment
			continue

		source_enrollment = source_enrollments[source_prin_id]
		if source_enrollment is None or source_enrollment.Scope != scope:
			continue

		if IPrincipal(source_enrollment.Principal, None) is None:
			log("Ignoring dup enrollment for %s", source_prin_id)
			continue

		index = 0
		section = None
		for idx, item in enumerate(items):
			section_name, estimated_seat_count = item.section_name, item.seat_count
			if estimated_seat_count < max_seat_count:
				index = idx
				section = parent.SubInstances[section_name]
				break

		if section is None:
			index = 0
			items.sort()
			section_name = items[0].section_name
			section = parent.SubInstances[section_name]

		dest_enrollments = IDefaultCourseInstanceEnrollmentStorage(section)
		if source_prin_id in dest_enrollments:
			continue

		if not dry_run:
			mover = IObjectMover(source_enrollment)
			mover.moveTo(dest_enrollments)

		count += 1
		items[index].seat_count += 1
		log("Move enrollment for principal %s to section %s", source_prin_id,
			section_name)

	return count

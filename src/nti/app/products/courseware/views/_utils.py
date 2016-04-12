#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope.component.hooks import getSite

from pyramid import httpexceptions as hexc

from nti.app.products.courseware.utils import encode_keys
from nti.app.products.courseware.utils import memcache_get
from nti.app.products.courseware.utils import memcache_set
from nti.app.products.courseware.utils import last_synchronized

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.common.string import TRUE_VALUES

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseAssignmentCatalog
from nti.contenttypes.courses.interfaces import ICourseAssessmentItemCatalog

from nti.contenttypes.courses.legacy_catalog import ILegacyCourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

def _get_self_assessments_for_course(course):
	"""
	Given an :class:`.ICourseInstance`, return a list of all
	the \"self assessments\" in the course. Self-assessments are
	defined as top-level question sets that are not used within an assignment
	in the course.
	"""

	# NOTE: This is pretty tightly coupled to the implementation
	# and the use of one content package (?). See NonAssignmentsByOutlineNodeDecorator
	# (TODO: Find a way to unify this)
	catalog = ICourseAssessmentItemCatalog(course)

	# Not only must we filter out assignments, we must filter out the
	# question sets that they refer to; we assume such sets are only
	# used by the assignment.

	result = list()
	qsids_to_strip = set()

	for item in catalog.iter_assessment_items():
		if IQAssignment.providedBy(item):
			qsids_to_strip.add(item.ntiid)
			for assignment_part in item.parts:
				question_set = assignment_part.question_set
				qsids_to_strip.add(question_set.ntiid)
				for question in question_set.questions:
					qsids_to_strip.add(question.ntiid)
		elif not IQuestionSet.providedBy(item):
			qsids_to_strip.add(item.ntiid)
		else:
			result.append(item)

	# Now remove the forbidden
	result = [x for x in result if x.ntiid not in qsids_to_strip]
	return result

def _get_self_polls_for_course(course):
	"""
	Given an :class:`.ICourseInstance`, return a list of all
	the \"self polls\" in the course. Self-polls are
	defined as top-level polls sets that are not used within an survey
	in the course.
	"""

	result = list()
	qsids_to_strip = set()
	catalog = ICourseAssessmentItemCatalog(course)

	for item in catalog.iter_assessment_items():
		if IQSurvey.providedBy(item):
			qsids_to_strip.add(item.ntiid)
			for poll in item.questions:
				qsids_to_strip.add(poll.ntiid)
		elif not IQPoll.providedBy(item):
			qsids_to_strip.add(item.ntiid)
		else:
			result.append(item)

	# Now remove the forbidden
	result = [x for x in result if x.ntiid not in qsids_to_strip]
	return result

def _do_get_containers_in_course(context):
	course = ICourseInstance(context)
	try:
		packages = course.ContentPackageBundle.ContentPackages
	except AttributeError:
		packages = (course.legacy_content_package,)

	def _recur(node, accum):
		# Get our embedded ntiids and recursively
		# fetch our children's ntiids
		ntiid = node.ntiid
		try:
			accum.update(node.embeddedContainerNTIIDs)
		except AttributeError:
			pass

		if ntiid:
			accum.add(ntiid)

		for n in node.children:
			_recur(n, accum)

	containers_in_course = set()
	for package in packages:
		_recur(package, containers_in_course)

	# Now fetch from our index
	catalog = get_library_catalog()
	if catalog is not None:
		sites = get_component_hierarchy_names()
		package_ntiids = (x.ntiid for x in packages)
		contained_objs = catalog.search_objects(container_ntiids=package_ntiids,
												container_all_of=False,
												sites=sites)
		# Do we need target_ntiid here?
		contained_ntiids = (x.ntiid for x in contained_objs)
		containers_in_course.update(contained_ntiids)

	# Add in our self-assessments
	catalog = ICourseAssessmentItemCatalog(course)
	ntiids = (x.ntiid for x in catalog.iter_assessment_items())
	containers_in_course = containers_in_course.union(ntiids)

	self_assessments = _get_self_assessments_for_course(course)
	self_assessment_qsids = (x.ntiid for x in self_assessments)
	self_assessment_containerids = (x.__parent__.ntiid for x in self_assessments)
	containers_in_course = containers_in_course.union(self_assessment_containerids)
	containers_in_course = containers_in_course.union(self_assessment_qsids)

	# Add in our assignments
	assignment_catalog = ICourseAssignmentCatalog(course)
	assignment_ntiids = (asg.ntiid for asg in assignment_catalog.iter_assignments())
	containers_in_course = containers_in_course.union(assignment_ntiids)
	containers_in_course.discard(None)
	return containers_in_course

def _get_containers_in_course(context):
	site = getSite().__name__
	entry = ICourseCatalogEntry(context)
	key = "/course/%s" % encode_keys(site, entry.ntiid, "containers", last_synchronized())
	containers = memcache_get(key)
	if containers is None:
		containers = _do_get_containers_in_course(context)
		memcache_set(key, containers)
	return containers

def _tx_string(s):
	if s and isinstance(s, unicode):
		s = s.encode('utf-8')
	return s

def _parse_user(values):
	username = values.get('username') or values.get('user')
	if not username:
		raise hexc.HTTPUnprocessableEntity(detail='No username')

	user = User.get_user(username)
	if not user or not IUser.providedBy(user):
		raise hexc.HTTPUnprocessableEntity(detail='User not found')

	return username, user

def _parse_courses(values):
	# get validate course entry
	ntiids = values.get('ntiid') or values.get('ntiids')
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()

	result = []
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		if not ILegacyCourseInstance.providedBy(context):
			context = ICourseCatalogEntry(context, None)
		if context is not None:
			result.append(context)
	return result

def _parse_course(values):
	result = _parse_courses(values)
	if not result:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	return result[0]

def is_true(s):
	return bool(s and s.lower() in TRUE_VALUES)

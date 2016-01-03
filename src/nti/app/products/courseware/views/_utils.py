#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views directly related to individual courses and course sub-objects.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
from urllib import unquote
from urlparse import urlparse

from zope.component.hooks import getSite

from plone.namedfile.file import getImageInfo
from plone.namedfile.interfaces import INamed

from slugify import slugify_filename

from nti.app.contentfile import to_external_download_href

from nti.assessment.interfaces import IQPoll
from nti.assessment.interfaces import IQSurvey
from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.common.random import generate_random_hex_string

from nti.contentfile.model import ContentBlobFile
from nti.contentfile.model import ContentBlobImage

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseAssignmentCatalog
from nti.contenttypes.courses.interfaces import ICourseAssessmentItemCatalog

from nti.ntiids.ntiids import find_object_with_ntiid
from nti.ntiids.ntiids import is_valid_ntiid_string as is_valid_ntiid

from nti.site.site import get_component_hierarchy_names

from ..utils import encode_keys
from ..utils import memcache_get
from ..utils import memcache_set
from ..utils import last_synchronized

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

def _slugify_in_container(text, container):
	separator = '_'
	newtext = slugify_filename(text)
	text_noe, ext = os.path.splitext(newtext)
	while True:
		s = generate_random_hex_string(6)
		newtext = "%s%s%s%s" % (text_noe, separator, s, ext)
		if newtext not in container:
			break
	return newtext

def _get_file_from_link(link):
	result = None
	try:
		if link.endswith('view') or link.endswith('download'):
			path = urlparse(link).path
			path = os.path.split(path)[0]
		else:
			path = link
		ntiid = unquote(os.path.split(path)[1] or u'')  # last part of path
		result = find_object_with_ntiid(ntiid) if is_valid_ntiid(ntiid) else None
		if INamed.providedBy(result):
			return result
	except Exception:
		pass  # Nope
	return None

def _get_namedfile(source, name=None):
	contentType = getattr(source, 'contentType', None)
	if contentType:
		factory = ContentBlobFile
	else:
		contentType, _, _ = getImageInfo(source)
		source.seek(0)  # reset
		factory = ContentBlobImage if contentType else ContentBlobFile
	contentType = contentType or u'application/octet-stream'
	result = factory()
	result.name = name
	# for filename we want to use the filename as originally provided on the source, not
	# the sluggified internal name. This allows us to give it back in the
	# Content-Disposition header on download
	result.filename = getattr(source, 'filename', None) or getattr(source, 'name', name)
	result.data = source.read()
	result.contentType = contentType
	return result

def _get_download_href(item):
	try:
		result = to_external_download_href(item)
		return result
	except Exception:
		pass  # Nope
	return None

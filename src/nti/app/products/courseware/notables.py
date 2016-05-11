#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Functions and architecture for general activity streams.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from BTrees.LFBTree import LFSet as Set

from nti.app.notabledata.interfaces import IUserPriorityCreatorNotableProvider

from nti.common.property import CachedProperty

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.contenttypes.courses.utils import get_enrollment_catalog

from nti.dataserver.contenttypes.forums.interfaces import IPersonalBlogComment

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import INotableFilter

from nti.dataserver.metadata_index import isTopLevelContentObjectFilter

from nti.metadata import dataserver_metadata_catalog

from nti.site.site import get_component_hierarchy_names

_FEEDBACK_MIME_TYPE = "application/vnd.nextthought.assessment.userscourseassignmenthistoryitemfeedback"

@interface.implementer(INotableFilter)
class TopLevelPriorityNotableFilter(object):
	"""
	Determines whether the object is a notable created by important
	creators (e.g. instructors of my courses).  These objects must also
	be top-level objects.
	"""

	def __init__(self, context):
		self.context = context

	def is_notable(self, obj, user):
		obj_creator = getattr(obj, 'creator', None)
		obj_creator = getattr(obj_creator, 'username', obj_creator)

		# Filter out blog comments that might cause confusion.
		if 		obj_creator is None \
			or 	IPersonalBlogComment.providedBy(obj) \
			or  obj_creator == user.username:
			return False

		# Note: pulled from metadata_index; first two params not used.
		if not isTopLevelContentObjectFilter(None, None, obj):
			return False

		# See if our creator is an instructor in a current course.
		# Only if shared with my course community.
		shared_with = getattr(obj, 'sharedWith', {})
		if shared_with:
			for enrollments in component.subscribers((user,),
													  IPrincipalEnrollments):
				for enrollment in enrollments.iter_enrollments():

					course = ICourseInstance(enrollment, None)
					catalog_entry = ICourseCatalogEntry(course, None)
					if 		course is None \
						or 	catalog_entry is None \
	 					or 	not catalog_entry.isCourseCurrentlyActive():  # pragma: no cover
						continue

					if obj_creator in (x.id for x in course.instructors):
						# TODO: Like in the provider below, implies?
						course_scope = course.SharingScopes[ enrollment.Scope ]
						if obj.isSharedDirectlyWith(course_scope):
							return True
		return False

@component.adapter(IUser, interface.Interface)
@interface.implementer(IUserPriorityCreatorNotableProvider)
class _UserPriorityCreatorNotableProvider(object):
	"""
	We want all items created by instructors shared with
	course communities the user is enrolled in.  If items
	are shared with global communities or other, perhaps
	older, courses, we should exclude those.

	We also return all feedback created by such instructors.
	We rely on permissioning to filter out non-relevant entries.
	"""

	def __init__(self, user, request):
		self.context = user

	@CachedProperty
	def _catalog(self):
		return dataserver_metadata_catalog()

	def _get_feedback_intids(self, instructor_intids):
		catalog = self._catalog
		query = {'any_of': (_FEEDBACK_MIME_TYPE,) }
		feedback_intids = catalog['mimeType'].apply(query)
		results = catalog.family.IF.intersection(instructor_intids, feedback_intids)
		return results

	def get_notable_intids(self):
		results = Set()
		catalog = self._catalog
		intids = component.getUtility(IIntIds)
		enrollment_catalog = get_enrollment_catalog()
		site_names = get_component_hierarchy_names()
		query = {
			IX_SITE:{'any_of': site_names},
			IX_USERNAME:{'any_of':(self.context.username,)}
		}
		for uid in enrollment_catalog.apply(query) or ():
			enrollment = intids.queryObject(uid)
			if not ICourseInstanceEnrollmentRecord.providedBy(enrollment):
				continue

			course = ICourseInstance(enrollment, None)
			catalog_entry = ICourseCatalogEntry(course, None)
			if 		course is None \
				or 	catalog_entry is None \
				or 	not catalog_entry.isCourseCurrentlyActive():  # pragma: no cover
				continue

			course_instructors = {x.id for x in course.instructors}
			instructor_intids = catalog['creator'].apply({'any_of': course_instructors})

			# TODO: Do we need implies?
			course_scope = course.SharingScopes[ enrollment.Scope ]
			scope_ntiids = (course_scope.NTIID,)
			course_shared_with_intids = catalog['sharedWith'].apply({'any_of': scope_ntiids})
			course_results = catalog.family.IF.intersection(instructor_intids,
															course_shared_with_intids)
			results.update(course_results)
			feedback_intids = self._get_feedback_intids(instructor_intids)
			results.update(feedback_intids)
		return results

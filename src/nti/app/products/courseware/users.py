#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import Mapping

from zope import component
from zope import interface
from zope.security.interfaces import IPrincipal

from nti.common.property import alias

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.dataserver.interfaces import IUser
from nti.dataserver.users.suggested_contacts import SuggestedContact
from nti.dataserver.users.suggested_contacts import SuggestedContactsProvider
from nti.dataserver.users.suggested_contacts import SuggestedContactRankingPolicy

from .utils import get_enrollment_record

from .interfaces import ISuggestedContactsProvider

class ClassmatesSuggestedContactRankingPolicy(SuggestedContactRankingPolicy):
	
	provider = alias('__parent__')
		
	def _skey(self, x):
		return (x.entry.StartDate, x.username)
	
	def sort(self, data):
		if isinstance(data, Mapping):
			result = []
			seen = set()
			data = sorted(data.items(), key=lambda x: self._skey(x[1]), reversed=True)
			for _, contacts in data:
				for contact in contacts:
					if contact not in seen:
						contact.entry = None
						result.append(contact)
		else:
			result = super(ClassmatesSuggestedContactRankingPolicy, self).sort(data)
		return result

@interface.implementer(ISuggestedContactsProvider)
class ClassmatesSuggestedContactsProvider(SuggestedContactsProvider):
	
	def __init__(self, *args, **kwargs):
		super(ClassmatesSuggestedContactsProvider, self).__init__(*args, **kwargs)
		self.ranking = ClassmatesSuggestedContactRankingPolicy()
		self.ranking.provider = self
	
	def iter_courses(self, user):
		for enrollments in component.subscribers( (user,), IPrincipalEnrollments):
			for enrollment in enrollments.iter_enrollments():
				course = ICourseInstance(enrollment, None)
				if course is not None:
					yield course
					
	def suggestions_by_course(self, user, context):
		record = get_enrollment_record(context, user)
		if record is None:
			return ()
		
		implies = set([record.Scope])
		for term in ENROLLMENT_SCOPE_VOCABULARY:
			if record.Scope == term.value:
				implies.update(term.implies)
				break
	
		result = []
		course = ICourseInstance(context)
		entry = ICourseCatalogEntry(context)
		for record in ICourseEnrollments(course).iter_enrollments():
			if record.Scope in implies:
				principal = IPrincipal(record.Principal, None)
				if principal is not None and IUser(principal) != user:
					suggestion = SuggestedContact(username=principal.id, rank=1)
					suggestion.entry = entry
					result.append(suggestion)
		return result
	
	def suggestions(self, user):
		data = {}
		for course in self.iter_courses(user):
			entry = ICourseCatalogEntry(course)
			suggestions = self.suggestions_by_course(user, course)
			data[entry.ntiid] = suggestions
		result = self.ranking.sort(data)
		return result

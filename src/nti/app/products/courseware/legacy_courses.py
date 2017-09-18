#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data and objects to assist in the migration of legacy courses.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#: A map from site (IComponents) name
#: to a list of tuples naming the course name, purchasable ID
#: and the scopes. finally, is a traversal path to get the course to move
#: enrollments to (relative to the course catalog folder)
KNOWN_LEGACY_COURSES_BY_SITE = {
	'alibra.nextthought.com': [
		('AlibraSC',
		 'tag:nextthought.com,2011-10:Alibra-course-AlibraSC',
		 {'public': 'AlibraSC.alibra.nextthought.com', 'restricted': None})],
	'augsfluoroscopy.nextthought.com': [
		('Fluoroscopy',
		 'tag:nextthought.com,2011-10:AUGS-course-Fluoroscopy',
		 {'public': 'Fluoroscopy.augs.nextthought.com', 'restricted': None})],
	'demo.nextthought.com': [],# demo.nextthought.com is subsite of eval
	'eval.nextthought.com': [
		('NTI101',
		 'tag:nextthought.com,2011-10:NTIEval-course-NTI101',
		 {'public': 'NTI101.eval.nextthought.com', 'restricted': None}),
		('ScienceClub',
		 'tag:nextthought.com,2011-10:NTIEval-course-ScienceClub',
		 {'public': 'ScienceClub.eval.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:scienceinstructor-MeetingRoom:Group-science.nextthought.com'})],
	'labs.symmys.com': [],
	'law.nextthought.com': [],
	'litworld.nextthought.com': [
		('LitClubSC',
		 'tag:nextthought.com,2011-10:LitWorld-course-LitClubSC',
		 {'public': 'LitClubSC.litworld.nextthought.com', 'restricted': None})],
	'mathcounts.nextthought.com': [],
	'oc.nextthought.com': [
		('BUSA5213',
		 'tag:nextthought.com,2011-10:OC-course-BUSA5213LegalAndRegulatoryIssues',
		 {'public': 'BUSA5213.oc.nextthought.com',
		  'restricted': 'BUSA5213Spring2014.oc.nextthought.com'})],
	'personalleadership.nextthought.com': [],
	'platform.ou.edu': [
		('ANTH1613',
		 'tag:nextthought.com,2011-10:OU-course-ANTH1613',
		 {'public': 'ANTH1613.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:swan3561-MeetingRoom:Group-anth1613spring2014.ou.nextthought.com'}),
		('ANTH4970',
		 'tag:nextthought.com,2011-10:OU-course-ANTH4970',
		 {'public': 'ANTH4970.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:lewi7532-MeetingRoom:Group-anth4970spring2014.ou.nextthought.com'}),
		('BIOL2124F2014',
		 'tag:nextthought.com,2011-10:OU-course-BIOL2124F2014',
		 {'public': 'BIOL2124F2014.ou.nextthought.com', 'restricted': None},
		 'Fall2014/BIOL 2124'),
		('CHEM1315',
		 'tag:nextthought.com,2011-10:OU-course-CHEM1315GeneralChemistry',
		 {'public': 'CHEM1315.ou.nextthought.com',
		  'restricted': 'CHEM1315Fall2013.ou.nextthought.com'}),
		('CHEM1315F2014',
		 'tag:nextthought.com,2011-10:OU-course-CHEM1315F2014',
		 {'public': 'CHEM1315F2014.ou.nextthought.com',
		  'restricted': 'CHEM1315Fall2014.ou.nextthought.com'},
		 'Fall2014/CHEM 1315'),
		('CHEM4970',
		 'tag:nextthought.com,2011-10:OU-course-CHEM4970',
		 {'public': 'CHEM4970.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:morv1533-MeetingRoom:Group-chem4970spring2014.ou.nextthought.com'}),
		('CHEM4970F2014',
		 'tag:nextthought.com,2011-10:OU-course-CHEM4970F2014',
		 {'public': 'CHEM4970F2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:morv1533-MeetingRoom:Group-chem4970fall2014.ou.nextthought.com'},
		 'Fall2014/CHEM 4970/SubInstances/100'),
		('CLC3403',
		 'tag:nextthought.com,2011-10:OU-course-CLC3403LawAndJustice',
		 {'public': 'CLC3403.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:harp4162-MeetingRoom:Group-clc3403fall2013.ou.nextthought.com'}),
		('CLC3403F2014',
		 'tag:nextthought.com,2011-10:OU-course-CLC3403F2014',
		 {'public': 'CLC3403F2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:harp4162-MeetingRoom:Group-clc3403fall2014.ou.nextthought.com'},
		 'Fall2014/CLC 3403'),
		('COMM4970',
		 'tag:nextthought.com,2011-10:OU-course-COMM4970',
		 {'public': 'COMM4970.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:dunb8859-MeetingRoom:Group-comm4970spring2014.ou.nextthought.com'}),
		('CS1300',
		 'tag:nextthought.com,2011-10:OU-course-CS1300',
		 {'public': 'CS1300.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:mcgo2121-MeetingRoom:Group-cs1300spring2014.ou.nextthought.com'}),
		('CS1323',
		 'tag:nextthought.com,2011-10:OU-course-CS1323',
		 {'public': 'CS1323.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:tryt3968-MeetingRoom:Group-cs1323spring2014.ou.nextthought.com'}),
		('CS1323SU2014',
		 'tag:nextthought.com,2011-10:OU-course-CS1323SU2014',
		 {'public': 'CS1323SU2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:tryt3968-MeetingRoom:Group-cs1323summer2014.ou.nextthought.com'}),
		('EDAH5023',
		 'tag:nextthought.com,2011-10:OU-course-EDAH5023',
		 {'public': 'EDAH5023.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:blac9783-MeetingRoom:Group-edah5023spring2014.ou.nextthought.com'}),
		('ENGR1510',
		 'tag:nextthought.com,2011-10:OU-course-ENGR1510',
		 {'public': 'ENGR1510.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:saba3508-MeetingRoom:Group-engr1510spring2014.ou.nextthought.com'}),
		('FIN3303',
		 'tag:nextthought.com,2011-10:OU-course-FIN3303',
		 {'public': 'FIN3303.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:megg4758-MeetingRoom:Group-fin3303spring2014.ou.nextthought.com'}),
		('GEOG3890',
		 'tag:nextthought.com,2011-10:OU-course-GEOG3890',
		 {'public': 'GEOG3890.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:puls2013-MeetingRoom:Group-geog3890spring2014.ou.nextthought.com'}),
		('GEOL1114',
		 'tag:nextthought.com,2011-10:OU-course-GEOL1114',
		 {'public': 'GEOL1114.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:elmo3302-MeetingRoom:Group-geol1114spring2014.ou.nextthought.com'}),
		('HSCI3013',
		 'tag:nextthought.com,2011-10:OU-course-HSCI3013',
		 {'public': 'HSCI3013.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:magr9201-MeetingRoom:Group-hsci3013spring2014.ou.nextthought.com'}),
		('IAS2003',
		 'tag:nextthought.com,2011-10:OU-course-IAS2003UnderstandingTheGlobalCommunity',
		 {'public': 'IAS2003.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:gril4990-MeetingRoom:Group-ias2003fall2013.ou.nextthought.com'}),
		('IAS2003F2014',
		 'tag:nextthought.com,2011-10:OU-course-IAS2003F2014',
		 {'public': 'IAS2003F2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:gril4990-MeetingRoom:Group-ias2003fall2014.ou.nextthought.com'},
		 'Fall2014/IAS 2003'),
		('METR2603',
		 'tag:nextthought.com,2011-10:OU-course-METR2603UnderstandingSevereAndUnusualWeather',
		 {'public': 'METR2603.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:post8922-MeetingRoom:Group-metr2603fall2013.ou.nextthought.com'}),
		('MGT2013',
		 'tag:nextthought.com,2011-10:OU-course-MGT2013',
		 {'public': 'MGT2013.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:shor1744-MeetingRoom:Group-mgt2013summer2014.ou.nextthought.com'}),
		('PHIL1203',
		 'tag:nextthought.com,2011-10:OU-course-PHIL1203PhilosophyAndHumanDestinyEastAndWest',
		 {'public': 'PHIL1203.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:judi5807-MeetingRoom:Group-phil1203fall2013.ou.nextthought.com'},),
		('PHIL1203F2014',
		 'tag:nextthought.com,2011-10:OU-course-PHIL1203F2014',
		 {'public': 'PHIL1203F2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:judi5807-MeetingRoom:Group-phil1203fall2014.ou.nextthought.com'},
		 'Fall2014/PHIL 1203'),
		('PSC4283',
		 'tag:nextthought.com,2011-10:OU-course-PSC4283',
		 {'public': 'PSC4283.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:wert4649-MeetingRoom:Group-psc4283spring2014.ou.nextthought.com'}),
		('SOC1113',
		 'tag:nextthought.com,2011-10:OU-course-SOC1113',
		 {'public': 'SOC1113.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:damp8528-MeetingRoom:Group-soc1113spring2014.ou.nextthought.com'}),
		('SOC1113F2014',
		 'tag:nextthought.com,2011-10:OU-course-SOC1113F2014',
		 {'public': 'SOC1113F2014.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:damp8528-MeetingRoom:Group-soc1113fall2014.ou.nextthought.com'},
		 'Fall2014/SOC 1113'),
		('SOC3123',
		 'tag:nextthought.com,2011-10:OU-course-SOC3123',
		 {'public': 'SOC3123.ou.nextthought.com',
		  'restricted': 'tag:nextthought.com,2011-10:peck6569-MeetingRoom:Group-soc3123fall2013.ou.nextthought.com'}),
		('UCOL1002F2014',
		 'tag:nextthought.com,2011-10:OU-course-UCOL1002F2014',
		 {'public': 'UCOL1002F2014.ou.nextthought.com', 'restricted': None},
		 'Fall2014/UCOL 1002')],
	'prmia.nextthought.com': [],
	'rwanda.nextthought.com': [],
	'symmys-alpha.nextthought.com': [],
	'symmys.nextthought.com': [],
	'testmathcounts.nextthought.com': [],
	'testprmia.nextthought.com': [],
	'utsa.nextthought.com': [
		('UTSAEval',
		 'tag:nextthought.com,2011-10:UTSA-course-UTSAEval',
		 {'public': 'UTSAEval.utsa.nextthought.com', 'restricted': None})]}

def get_scopes_for_purchasable_ntiid(ntiid):
	for _, site_courses in KNOWN_LEGACY_COURSES_BY_SITE.items():
		for info in site_courses:
			if info[1] == ntiid:
				return info[2]

def get_scopes_from_course_element(course_element):
	if course_element is not None:
		legacy_scopes = {'public': None, 'restricted': None}
		for scope in course_element.xpath(b'scope'):
			type_ = scope.get(b'type', '').lower()
			entries = scope.xpath(b'entry')
			entity_id = entries[0].text if entries else None
			if type_ and entity_id:
				legacy_scopes[type_] = entity_id
		return legacy_scopes


from nti.site.site import get_site_for_site_names
from nti.site.interfaces import IHostPolicyFolder

from zope.traversing.interfaces import IEtcNamespace

from zope.security.interfaces import IPrincipal

from zope.component.hooks import site as current_site

from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage
from nti.contenttypes.courses.enrollment import DefaultCourseInstanceEnrollmentRecord
from nti.contenttypes.courses.enrollment import global_course_catalog_enrollment_storage

from nti.dataserver.interfaces import IEntityContainer

from nti.dataserver.users.entity import Entity

from .interfaces import ILegacyCommunityBasedCourseInstance

from zope import component
from zope.intid import IIntIds
from ZODB.interfaces import IConnection

def _migrate_enrollments():

	intids  = component.getUtility(IIntIds)

	for site_name, site_courses in sorted(KNOWN_LEGACY_COURSES_BY_SITE.items()):
		if not site_courses:
			continue

		site = get_site_for_site_names((site_name,))
		if not IHostPolicyFolder.providedBy(site):
			logger.warn("No persistent site %s, not migrating", site_name)
			continue

		with current_site(site):
			# Must do this in the right site so the registration goes
			# in the right catalog place

			prin_storage = global_course_catalog_enrollment_storage(None)

			for value in site_courses:
				course_name = value[0]
				course_id = value[1]
				scopes = value[2]

				community = Entity.get_entity(scopes['public'])
				restricted = ()
				if scopes.get('restricted'):
					restricted = IEntityContainer(Entity.get_entity(scopes['restricted']), ())

				if community is None:
					logger.warn("No community %s, not migrating course %s/%s", course_name, course_id)
					continue

				course = ILegacyCommunityBasedCourseInstance(community, None)
				if course is None:
					logger.warn("No course instance found for %s/%s, not migrating", course_name, course_id)
					continue

				modern_enrollment_storage = IDefaultCourseInstanceEnrollmentStorage(course)
				if modern_enrollment_storage._p_jar is None:
					# Pick a database for these
					IConnection(modern_enrollment_storage).add(modern_enrollment_storage)
				legacy_enrollments = _LegacyCourseInstanceEnrollments(course, community, restricted)

				added = []

				for record in legacy_enrollments.iter_enrollments():
					principal = record.Principal
					principal_id = IPrincipal(principal).id

					if principal_id in modern_enrollment_storage: # Done this once
						continue

					added.append(principal_id)
					record = DefaultCourseInstanceEnrollmentRecord(Principal=principal,
																   Scope=record.Scope)

					prin_enrollments = prin_storage.enrollments_for_id(principal_id, principal)
					prin_enrollments._p_jar.add(record) # pick a database
					prin_enrollments.add(record)

					# avoid firing an event...
					record.__parent__ = modern_enrollment_storage
					record.__name__ = principal_id
					# ...but these should have an intid
					intids.register(record)

					modern_enrollment_storage[principal_id] = record

				logger.info("Recorded enrollments for %s: %s", course.__name__, added)

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT

class _LegacyCourseInstanceEnrollments(object):

	def __init__( self, context, community, forcredit ):
		self.context = context
		self.__parent__ = context
		self.community = community
		self.forcredit = forcredit

	def iter_enrollments(self):
		course = self.context
		community = self.community
		forcredit = self.forcredit
		instructor_usernames = {x.username for x in self.context.instructors}
		for member in community.iter_members():
			scope = ES_PUBLIC if member not in forcredit else ES_CREDIT
			if member.username in instructor_usernames:
				scope = ES_CREDIT

			record = DefaultCourseInstanceEnrollmentRecord(CourseInstance=course,
														   Scope=scope,
														   Principal=member)
			yield record

from zope.traversing.api import traverse

from pyramid.threadlocal import get_current_request

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.enrollment import migrate_enrollments_from_course_to_course

def _copy_enrollments_from_legacy_to_new(request=None):
	"""
	Returns an informative data structure..
	"""

	result = []
	if request is None:
		request = get_current_request()

	hostsites = component.getUtility(IEtcNamespace,name='hostsites')
	for site_name, site_courses in sorted(KNOWN_LEGACY_COURSES_BY_SITE.items()):
		if not site_courses:
			result.append(("Nothing in site", site_name))
			continue

		site = hostsites.get(site_name)
		if not IHostPolicyFolder.providedBy(site):
			logger.warn("No persistent site %s/%s, not migrating", site_name, site)
			result.append(("No persistent site", site_name))
			continue

		with current_site(site):
			# Must do this in the right site so the registration goes
			# in the right catalog place

			catalog = component.getUtility(ICourseCatalog)

			for value in site_courses:
				if len(value) < 4:
					continue

				course_name = value[0]
				course_id = value[1]
				scopes = value[2]
				path_to_new_course = value[3]

				community = Entity.get_entity(scopes['public'])
				if community is None:
					logger.warn("No community %s, not migrating course %s/%s",
								scopes['public'], course_name, course_id)
					result.append((path_to_new_course, 'No community', scopes))
					continue

				old_course = ILegacyCommunityBasedCourseInstance(community, None)
				if old_course is None:
					logger.warn("No course instance found for %s/%s, not migrating", course_name, course_id)
					result.append((path_to_new_course, 'No legacy course'))
					continue

				new_course = traverse(catalog, path_to_new_course, default=None, request=request)
				if new_course is None:
					logger.warn("No new course instance found at %s, not migrating", path_to_new_course)
					result.append((path_to_new_course, 'No new course', path_to_new_course))
					continue

				logger.info("Copying enrollments from %s/%s to %s",
							course_name, course_id, path_to_new_course)

				count = migrate_enrollments_from_course_to_course(old_course, new_course)
				logger.info("Copied %d enrollments to %s", path_to_new_course)

				result.append((path_to_new_course,count))
	return result

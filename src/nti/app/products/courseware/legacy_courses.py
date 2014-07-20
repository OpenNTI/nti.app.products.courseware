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
#: to a list of tuples naming the purchasable ID
#: and the corresponding legacy community name.
KNOWN_LEGACY_COURSES_BY_SITE = {
	'alibra.nextthought.com': [
		('tag:nextthought.com,2011-10:Alibra-course-AlibraSC',
		 'AlibraSC.alibra.nextthought.com')],
	'augsfluoroscopy.nextthought.com': [
		('tag:nextthought.com,2011-10:AUGS-course-Fluoroscopy',
		 'Fluoroscopy.augs.nextthought.com')],
	'columbia.nextthought.com': [],
	'demo.nextthought.com': [], # demo.nextthought.com is subsite of eval
	'eval.nextthought.com': [
		('tag:nextthought.com,2011-10:NTIEval-course-ScienceClub',
		 'ScienceClub.eval.nextthought.com'),
		('tag:nextthought.com,2011-10:NTIEval-course-NTI101',
		 'NTI101.eval.nextthought.com')],
	'labs.symmys.com': [],
	'law.nextthought.com': [],
	'litworld.nextthought.com': [
		('tag:nextthought.com,2011-10:LitWorld-course-LitClubSC',
		 'LitClubSC.litworld.nextthought.com')],
	'mathcounts.nextthought.com': [],
	'oc.nextthought.com': [
		('tag:nextthought.com,2011-10:OC-course-BUSA5213LegalAndRegulatoryIssues',
		 'BUSA5213.oc.nextthought.com')],
	'personalleadership.nextthought.com': [],
	'platform.ou.edu': [
		('tag:nextthought.com,2011-10:OU-course-ANTH1613',
		 'ANTH1613.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-ANTH4970',
		 'ANTH4970.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-BIOL2124F2014', # MIGRATE
		 'BIOL2124F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CHEM1315F2014', # MIGRATE
		 'CHEM1315F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CHEM1315GeneralChemistry',
		 'CHEM1315.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CHEM4970',
		 'CHEM4970.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CHEM4970F2014', # MIGRATE
		 'CHEM4970F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CLC3403F2014', # MIGRATE
		 'CLC3403F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CLC3403LawAndJustice',
		 'CLC3403.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-COMM4970',
		 'COMM4970.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CS1300',
		 'CS1300.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CS1323',
		 'CS1323.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-CS1323SU2014',
		 'CS1323SU2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-EDAH5023',
		 'EDAH5023.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-ENGR1510',
		 'ENGR1510.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-FIN3303',
		 'FIN3303.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-GEOG3890',
		 'GEOG3890.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-GEOL1114',
		 'GEOL1114.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-HSCI3013',
		 'HSCI3013.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-IAS2003F2014', # MIGRATE
		 'IAS2003F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-IAS2003UnderstandingTheGlobalCommunity',
		 'IAS2003.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-METR2603UnderstandingSevereAndUnusualWeather',
		 'METR2603.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-MGT2013',
		 'MGT2013.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-PHIL1203F2014', # MIGRATE
		 'PHIL1203F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-PHIL1203PhilosophyAndHumanDestinyEastAndWest',
		 'PHIL1203.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-PSC4283',
		 'PSC4283.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-SOC1113',
		 'SOC1113.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-SOC1113F2014', # MIGRATE
		 'SOC1113F2014.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-SOC3123',
		 'SOC3123.ou.nextthought.com'),
		('tag:nextthought.com,2011-10:OU-course-UCOL1002F2014', # MIGRATE
		 'UCOL1002F2014.ou.nextthought.com')],
	'prmia.nextthought.com': [],
	'rwanda.nextthought.com': [],
	'symmys-alpha.nextthought.com': [],
	'symmys.nextthought.com': [],
	'testmathcounts.nextthought.com': [],
	'testprmia.nextthought.com': [],
	'utsa.nextthought.com': [
		('tag:nextthought.com,2011-10:UTSA-course-UTSAEval',
		 'UTSAEval.utsa.nextthought.com')]
}

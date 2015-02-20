#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

from zope import component 
from zope.security.interfaces import IPrincipal
from zope.copypastemove.interfaces import IObjectMover

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.contenttypes.courses.enrollment import SectionSeat
from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage

from nti.dataserver.users import User

from nti.dataserver.utils import run_with_dataserver
from nti.dataserver.utils.base_script import set_site
from nti.dataserver.utils.base_script import create_context

from nti.ntiids.ntiids import find_object_with_ntiid

def _migrate(ntiid, scope=ES_PUBLIC, max_seat_count=25, sections=(),
			 site=None, dry_run=False, verbose=False):
	if site:
		set_site(site)
		
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
			## dup enrollment
			continue
		
		source_enrollment = source_enrollments[source_prin_id]
		if source_enrollment is None or source_enrollment.Scope != scope:
			continue
	
		if IPrincipal(source_enrollment.Principal, None) is None:
			logger.warn("Ignoring dup enrollment for %s", source_prin_id)
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
		
		count +=1
		items[index].seat_count += 1
		log("Move enrollment for principal %s to section %s", source_prin_id,
			section_name)

	return count

def main():
	arg_parser = argparse.ArgumentParser(description="Migrate enrollments from main course to sub-instances" )
	arg_parser.add_argument('ntiid', help="Course entry identifier/ntiid")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							dest='verbose')
	arg_parser.add_argument('-c', '--count',
							dest='max_seat_count',
							default=25,
							type=int,
							help="Max seat count")
	arg_parser.add_argument('--sections',
							 dest='sections',
							 nargs="+",
							 default=(),
							 help="The names of sections to enroll")
	arg_parser.add_argument('--dry',
							 dest='dry_run',
							 action='store_true',
							 help="Dry run")
	arg_parser.add_argument('-s', '--scope',
							 dest='scope',
							 default=ES_PUBLIC,
							 help="Scope to migrate")
	arg_parser.add_argument('--site',
							dest='site',
							help="Application SITE.")
	args = arg_parser.parse_args()

	env_dir = os.getenv('DATASERVER_DIR')
	if not env_dir or not os.path.exists(env_dir) and not os.path.isdir(env_dir):
		raise IOError("Invalid dataserver environment root directory")

	site = args.site
	ntiid = args.ntiid
	scope = args.scope
	dry_run = args.dry_run
	sections = args.sections
	max_seat_count = args.max_seat_count
	
	if max_seat_count <= 0:
		raise ValueError("Invalid max seat count")
	
	context = create_context(env_dir, with_library=True)
	conf_packages = ('nti.appserver',)
	
	run_with_dataserver( environment_dir=env_dir,
						 xmlconfig_packages=conf_packages,
						 verbose=args.verbose,
						 context=context,
						 function=lambda: _migrate(site=site,
												   ntiid=ntiid,
												   scope=scope,
												   dry_run=dry_run,
												   sections=sections,
												   verbose=args.verbose,
												   max_seat_count=max_seat_count))
	sys.exit( 0 )

if __name__ == '__main__':
	main()

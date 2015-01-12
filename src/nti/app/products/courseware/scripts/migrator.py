#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

from nti.monkey import relstorage_patch_all_except_gevent_on_import
relstorage_patch_all_except_gevent_on_import.patch()

logger = __import__('logging').getLogger(__name__)

import os
import sys
import argparse

import zope.browserpage

from zope import component 
from zope.component import hooks
from zope.container.contained import Contained
from zope.security.interfaces import IPrincipal
from zope.configuration import xmlconfig, config
from zope.dottedname import resolve as dottedname
from zope.copypastemove.interfaces import IObjectMover

from z3c.autoinclude.zcml import includePluginsDirective

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.contenttypes.courses.enrollment import SectionSeat
from nti.contenttypes.courses.enrollment import IDefaultCourseInstanceEnrollmentStorage

from nti.dataserver.users import User
from nti.dataserver.utils import run_with_dataserver

from nti.site.site import get_site_for_site_names

class PluginPoint(Contained):

    def __init__(self, name):
        self.__name__ = name

PP_APP = PluginPoint('nti.app')
PP_APP_SITES = PluginPoint('nti.app.sites')
PP_APP_PRODUCTS = PluginPoint('nti.app.products')

def _migrate(ntiid, scope=ES_PUBLIC, max_seat_count=25, sections=(),
             site=None, dry_run=False, verbose=False):
    if site:
        cur_site = hooks.getSite()
        new_site = get_site_for_site_names( (site,), site=cur_site )
        if new_site is cur_site:
            raise ValueError("Unknown site name", site)
        hooks.setSite(new_site)

    catalog = component.getUtility(ICourseCatalog)
    try:
        catalog_entry = catalog.getCatalogEntry(ntiid)
    except KeyError:
        raise ValueError("Invalid course indentifier")

    parent = course = ICourseInstance(catalog_entry)
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

def _create_context(env_dir):
    etc = os.getenv('DATASERVER_ETC_DIR') or os.path.join(env_dir, 'etc')
    etc = os.path.expanduser(etc)

    context = config.ConfigurationMachine()
    xmlconfig.registerCommonDirectives(context)
        
    slugs = os.path.join(etc, 'package-includes')
    if os.path.exists(slugs) and os.path.isdir(slugs):
        package = dottedname.resolve('nti.dataserver')
        context = xmlconfig.file('configure.zcml', package=package, context=context)
        xmlconfig.include(context, files=os.path.join(slugs, '*.zcml'),
                          package='nti.appserver')

    library_zcml = os.path.join(etc, 'library.zcml')
    if os.path.exists(library_zcml):
        xmlconfig.include(context, file=library_zcml)
    else:
        logger.warn("Library not loaded")
    
    # Include zope.browserpage.meta.zcm for tales:expressiontype
    # before including the products
    xmlconfig.include(context, file="meta.zcml", package=zope.browserpage)

    # include plugins
    includePluginsDirective(context, PP_APP)
    includePluginsDirective(context, PP_APP_SITES)
    includePluginsDirective(context, PP_APP_PRODUCTS)
    
    return context

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
    
    context = _create_context(env_dir)
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

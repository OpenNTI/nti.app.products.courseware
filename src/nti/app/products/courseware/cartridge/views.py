#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
import tempfile

from lxml import etree

from pyramid.view import view_config

from zope.component import subscribers

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.cartridge.cartridge import build_cartridge_content
from nti.app.products.courseware.cartridge.cartridge import build_manifest_items

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import ICanvasWikiContent
from nti.app.products.courseware.cartridge.interfaces import ICartridgeWebContent
from nti.app.products.courseware.cartridge.interfaces import IIMSAssociatedContent
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge
from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridgeExtension

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


@view_config(route_name='objects.generic.traversal',
             request_method='GET',
             renderer='rest',
             context=ICourseInstance,
             permission=nauth.ACT_READ,
             name='common_cartridge')
class CommonCartridgeExportView(AbstractAuthenticatedView):

    def _export_to_filesystem(self, cartridge):
        tree = cartridge.manifest_resources
        archive = tempfile.mkdtemp()
        non_cc = os.path.join(archive, unicode('non_cc_assessments'))
        os.makedirs(non_cc)
        for extension in subscribers((cartridge,), IIMSCommonCartridgeExtension):
            extension.extend(archive)
        for (identifier, cc_resource) in cartridge.resources.items():
                if cc_resource is not None:
                    prepath = ''
                    if ICartridgeWebContent.providedBy(cc_resource):
                        prepath = 'web_resources'
                    elif ICanvasWikiContent.providedBy(cc_resource):
                        prepath = 'wiki_content'
                    target = os.path.join(archive, prepath)
                    try:
                        cc_resource.export(target)
                    except CommonCartridgeExportException as e:
                        logger.warn(e.message)
                        cartridge.errors.append(e)
                        continue
                    if getattr(cc_resource, 'dirname', None):
                        prepath = os.path.join(prepath, cc_resource.dirname)
                    href = os.path.join(prepath, cc_resource.filename)
                    item = etree.SubElement(tree, u'resource',
                                            identifier=unicode(cc_resource.identifier),
                                            type=cc_resource.type,
                                            href=href)
                    etree.SubElement(item, u'file', href=href)
                    # TODO need to recur on deps here (One reason video transcripts dont appear)
                    if getattr(cc_resource, 'dependencies', None):
                        for (dep_directory, deps) in cc_resource.dependencies.items():
                            for dep in deps:
                                if not IIMSAssociatedContent.providedBy(dep):
                                    dep_href = os.path.join('web_resources', dep_directory, dep.filename)
                                else:
                                    dep_href = os.path.join(dep_directory, dep.filename)
                                etree.SubElement(item, u'dependency', identifierref=unicode(dep.identifier))
                                dep_xml = etree.SubElement(tree, u'resource', identifier=unicode(dep.identifier),
                                                           type=dep.type,
                                                           href=dep_href)
                                etree.SubElement(dep_xml, u'file', href=dep_href)
                                if not IIMSAssociatedContent.providedBy(dep):
                                    dep_path = os.path.join(archive, 'web_resources', dep_directory)
                                else:
                                    dep_path = os.path.join(archive, dep_directory)
                                try:
                                    dep.export(dep_path)
                                except CommonCartridgeExportException as e:
                                    logger.warn(e.message)
                                    cartridge.errors.append(e)
        return archive

    def __call__(self):
        try:
            cartridge = IIMSCommonCartridge(self.context)
            # Process everything in the course
            xml = build_manifest_items(cartridge)
            build_cartridge_content(cartridge)
            archive = self._export_to_filesystem(cartridge)
            cartridge.export_errors(archive)
            renderer = get_renderer("manifest", ".pt", package='nti.app.products.courseware.cartridge')
            context = {
                'items': xml,
                'resources': ''.join(etree.tounicode(child, pretty_print=True) for child in cartridge.manifest_resources.iterchildren())
            }
            manifest = execute(renderer, {'context': context})
            with open(archive + '/imsmanifest.xml', 'w') as fd:
                fd.write(manifest.encode('utf-8'))
            zipped = shutil.make_archive('common_cartridge', 'zip', archive)
            filename = self.context.title + '.imscc'
            self.request.response.content_encoding = 'identity'
            self.request.response.content_type = 'application/zip; charset=UTF-8'
            self.request.response.content_disposition = 'attachment; filename="%s"' % filename
            self.request.response.body_file = open(zipped, "rb")
        finally:
            self.request.environ['nti.commit_veto'] = 'abort'
        return self.request.response


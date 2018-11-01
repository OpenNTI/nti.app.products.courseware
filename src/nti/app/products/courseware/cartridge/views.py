#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import shutil
import tempfile
import zipfile

from lxml import etree
from pyramid.view import view_config
from zope import component
from zope.component import subscribers
from zope.intid import IIntIds

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.products.courseware.cartridge.cartridge import build_manifest_items, build_cartridge_content

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge, IIMSManifestResources, \
    IIMSCommonCartridgeExtension, ICartridgeWebContent, ICanvasWikiContent
from nti.app.products.courseware.cartridge.renderer import get_renderer, execute

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

    def __call__(self):
        cartridge = IIMSCommonCartridge(self.context)
        tree = component.getUtility(IIMSManifestResources)
        xm_tee = tree()
        intids = component.getUtility(IIntIds)
        from IPython.terminal.debugger import set_trace;set_trace()

        # Process everything in the course
        xml = build_manifest_items(cartridge)
        build_cartridge_content(cartridge)
        # At this point every item in the course should have been appropriately marked
        # We just need to actually export the files, handle extensions, and update the resources section of the manifest
        archive = tempfile.mkdtemp()
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
                    cc_resource.export(target)
                    href = prepath + '/' + cc_resource.filename
                    item = etree.SubElement(xm_tee, u'resource',
                                            identifier=unicode(cc_resource.identifier),
                                            type=cc_resource.type,
                                            href=href)
                    etree.SubElement(item, u'file', href=href)
                # TODO rework dependencies
                # if cc_resource.dependencies:
                #     for (dep_directory, deps) in cc_resource.dependencies.items():
                #         for dep in deps:
                #             dep.export(archive + resource_dir + '/' + item.dirname + '/' + dep_directory)
        from IPython.terminal.debugger import set_trace;set_trace()
        renderer = get_renderer("manifest", ".pt", package='nti.app.products.courseware.cartridge')
        context = {
            'items': xml,
            'resources': ''.join(etree.tostring(child, pretty_print=True) for child in xm_tee.iterchildren())
        }
        manifest = execute(renderer, {'context': context})
        with open(archive + '/imsmanifest.xml', 'w') as fd:
            fd.write(manifest)
        zipped = shutil.make_archive('common_cartridge', 'zip', archive)
        filename = self.context.title + '.zip'  # TODO make imscc when done
        self.request.response.content_encoding = 'identity'
        self.request.response.content_type = 'application/zip; charset=UTF-8'
        self.request.response.content_disposition = 'attachment; filename="%s"' % filename
        self.request.response.body_file = open(zipped, "rb")
        return self.request.response

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

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.products.courseware.cartridge.cartridge import build_manifest_items

from nti.app.products.courseware.cartridge.interfaces import IIMSCommonCartridge, IIMSManifestResources, \
    IIMSCommonCartridgeExtension
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
        content = cartridge.cartridge_web_content
        xml = build_manifest_items(cartridge)
        archive = tempfile.mkdtemp()
        for extension in subscribers((cartridge,), IIMSCommonCartridgeExtension):
            extension.extend(archive)
        for (directory, items) in content.items():
            for item in items.values():
                resource_dir = '/web_resources/%s' % directory
                item.export(archive + resource_dir)
                if item.dependencies:
                    for (dep_directory, deps) in item.dependencies.items():
                        for dep in deps:
                            dep.export(archive + resource_dir + '/' + item.dirname + '/' + dep_directory)
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
        filename = self.context.title + '.imscc'
        self.request.response.content_encoding = 'identity'
        self.request.response.content_type = 'application/zip; charset=UTF-8'
        self.request.response.content_disposition = 'attachment; filename="%s"' % filename
        self.request.response.body_file = open(zipped, "rb")
        return self.request.response

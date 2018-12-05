#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from bs4 import BeautifulSoup
from pynliner import Pynliner
from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.contentfolder.utils import get_file_from_cf_io_url

from nti.app.contenttypes.presentation.decorators.assets import CONTENT_MIME_TYPE

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import ICartridgeWebContent, ICanvasWikiContent
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit
from nti.app.products.courseware.cartridge.interfaces import IIMSWebLink

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent, IMSWebContent
from nti.app.products.courseware.qti.utils import update_external_resources

from nti.contentlibrary.interfaces import IContentPackage
from nti.contentlibrary.interfaces import IFilesystemBucket
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit, ICartridgeWebContent)
class IMSWebContentResource(AbstractIMSWebContent):
    """
    pdf, ppt, docx, etc
    """

    @Lazy
    def href(self):
        return self.context.href

    @Lazy
    def filename(self):
        return os.path.basename(self.href)

    def export(self, path):
        package = find_interface(self.context, IContentPackage, strict=False)
        root = getattr(package, 'root', None)
        if not IFilesystemBucket.providedBy(root):
            if self.context.href.startswith('/dataserver2/cf.io/'):
                resource = get_file_from_cf_io_url(self.context.href)
                filename = os.path.basename(self.context.href)
                target_path = os.path.join(path, filename)
                self.copy_file_resource(resource, target_path)
            else:
                logger.warning("Unsupported bucket Boto?")
                # raise CommonCartridgeExportException(u"Unable to locate file on disk for %s. Is this resource "
                #                                     u"stored on Boto?" % self.context.label)
        elif self.context.href and root:
            source_path = os.path.join(root.absolute_path, self.context.href)
            filename = os.path.basename(source_path)
            target_path = os.path.join(path, filename)
            self.copy_resource(source_path, target_path)
        else:
            logger.warning(u"Unable to locate a content package for %s" % self.context.label)
            # raise CommonCartridgeExportException(u"Unable to locate a content package for %s" % self.context.label)


@interface.implementer(IIMSWebContentUnit, ICanvasWikiContent)
class IMSWebContentNativeReading(AbstractIMSWebContent):
    """
    A content package that is rendered into web content
    """

    @Lazy
    def rendered_package(self):
        # TODO logging
        return find_object_with_ntiid(self.context.target)

    @Lazy
    def rendered_package_path(self):
        return self.rendered_package.key.absolute_path

    def content_soup(self, styled=True):
        text = self.rendered_package.read_contents()
        if styled:
            # This inlines external style sheets
            content = Pynliner()
            content.root_url = self.rendered_package_path
            assert getattr(content, '_get_url', None)  # If this private method gets refactored, let us know
            # By default, this tries to retrieve via request, we will override
            content._get_url = lambda url: open(url).read().decode()
            content.from_string(text)
            text = content.run()
        return BeautifulSoup(text, features='html5lib')

    @Lazy
    def title(self):
        # TODO when to use title vs label, fallback etc....
        return self.context.label

    @Lazy
    def filename(self):
        return self.identifier + '.html'

    @Lazy
    def content(self):
        html = self.content_soup().find('body').prettify()
        html, dependencies = update_external_resources(html)
        self.dependencies['dependencies'].extend([IMSWebContent(self.context, dep) for dep in dependencies])
        return html

    def export(self, archive):
        renderer = get_renderer('native_reading', '.pt')
        context = {'identifier': self.identifier,
                   'title': self.title,
                   'body': self.content}
        html = execute(renderer, {'context': context})
        path_to = os.path.join(archive, self.filename)
        self.write_resource(path_to, html)
        return True


def related_work_factory(related_work):
    """
    Parses a related work into an IMS web link if it is an external link,
    a Native Reading Web Content unit if it is a content unit, or
    a Resource Web Content unit if it is a local resource (pdf, etc)
    """
    # Web Links => IMS Web Links
    if related_work.type == 'application/vnd.nextthought.externallink' and\
            bool(urllib_parse.urlparse(related_work.href).scheme):
        return IMSWebLink(related_work)
    # Native readings => IMS Learning Application Objects TODO
    elif related_work.type == CONTENT_MIME_TYPE:
        return IMSWebContentNativeReading(related_work)
    # Resource links => IMS Web Content
    else:
        return IMSWebContentResource(related_work)


def related_work_resource_factory(related_work):
    # This factory is used when we parse all of the catalog for related work refs
    # We only want to return concrete resources in that case, not links or native readings
    # If you enable native readings here you will get legacy course structure files
    if related_work.type == 'application/vnd.nextthought.externallink' and\
            bool(urllib_parse.urlparse(related_work.href).scheme):
        return None
    # Native readings => IMS Learning Application Objects
    elif related_work.type == CONTENT_MIME_TYPE:
        return None
    # Resource links => IMS Web Content
    else:
        return IMSWebContentResource(related_work)


@interface.implementer(IIMSWebLink)
class IMSWebLink(object):

    createFieldProperties(IIMSWebLink)

    extension = '.xml'

    def __init__(self, context):
        self.context = context

    @Lazy
    def filename(self):
        return unicode(self.identifier) + self.extension

    @Lazy
    def intids(self):
        return component.getUtility(IIntIds)

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)

    def create_dirname(self, path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    def write_resource(self, path, resource):
        self.create_dirname(path)
        with open(path, 'w') as fd:
            fd.write(resource.encode('utf-8'))
        return True

    def export(self, archive):
        renderer = get_renderer("web_link", ".pt")
        context = {
            'href': self.context.href,
            'title': self.context.label
        }
        xml = execute(renderer, {"context": context})
        path = os.path.join(archive, self.filename)
        self.write_resource(path, xml)

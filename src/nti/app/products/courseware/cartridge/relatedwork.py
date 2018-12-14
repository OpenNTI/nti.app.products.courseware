#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import os

from bs4 import BeautifulSoup, NavigableString
from premailer import transform, Premailer
from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.contentfolder.utils import get_file_from_cf_io_url

from nti.app.contenttypes.presentation.decorators.assets import CONTENT_MIME_TYPE, _path_exists_in_package, \
    _get_item_content_package

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import ICartridgeWebContent, ICanvasWikiContent
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit
from nti.app.products.courseware.cartridge.interfaces import IIMSWebLink

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent, IMSWebContent
from nti.app.products.courseware.qti.utils import update_external_resources
from nti.common import random

from nti.contentlibrary.interfaces import IContentPackage, IContentPackageLibrary
from nti.contentlibrary.interfaces import IFilesystemBucket
from nti.contentlibrary_rendering.interfaces import IContentPackageRenderMetadata
from nti.externalization import to_external_object
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IIMSWebContentUnit, ICartridgeWebContent)
class IMSWebContentResource(AbstractIMSWebContent):
    """
    pdf, ppt, docx, etc
    """

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def href(self):
        return self.context.href

    @Lazy
    def filename(self):
        # We add a hash in front here because these may be in mulitple content pacakges
        # When this happens we get into a situation where multiple ids point to the same file
        # because it's name is the same. Rather than adding the entire id we do random so the name is
        # still easy to read
        return random.generate_random_string(4) + '_' + os.path.basename(self.href)

    def export(self, path):
        package = find_interface(self.context, IContentPackage, strict=False)
        if package is None and getattr(self.context, 'target', False):
            target = find_object_with_ntiid(self.context.target)
            package = find_interface(target, IContentPackage, strict=False)
        if package is None:
            for name in ('href', 'icon'):
                value = getattr(self.context, name, None)
                if value and not value.startswith('/') and '://' not in value:
                    if package is None \
                            or not _path_exists_in_package(value, package):
                        # We make sure each url is in the correct package.
                        package = _get_item_content_package(self.context, value)
        root = getattr(package, 'root', None)
        if not IFilesystemBucket.providedBy(root):
            if self.context.href.startswith('/dataserver2/cf.io/'):
                resource = get_file_from_cf_io_url(self.context.href)
                target_path = os.path.join(path, self.filename)
                self.copy_file_resource(resource, target_path)
            else:
                logger.warning("Unsupported bucket Boto?")
                raise CommonCartridgeExportException(u"Unable to locate file on disk for %s. Is this resource "
                                                    u"stored on Boto?" % self.context.label)
        elif self.context.href and root:
            source_path = os.path.join(root.absolute_path, self.context.href)
            target_path = os.path.join(path, self.filename)
            self.copy_resource(source_path, target_path)
        else:
            logger.warning(u"Unable to locate a content package for %s" % self.context.label)
            raise CommonCartridgeExportException(u"Unable to locate a content package for %s" % self.context.label)


@interface.implementer(IIMSWebContentUnit, ICanvasWikiContent)
class IMSWebContentNativeReading(AbstractIMSWebContent):
    """
    A content package that is rendered into web content
    """

    @Lazy
    def rendered_package(self):
        rendered_package = find_object_with_ntiid(self.context.target)
        metadata = IContentPackageRenderMetadata(rendered_package, None)
        if metadata is not None:
            if not metadata.mostRecentRenderJob().is_success():
                raise CommonCartridgeExportException(u'Related work ref %s failed to render.' % self.title)
        return rendered_package

    @Lazy
    def rendered_package_path(self):
        return self.rendered_package.key.absolute_path

    def content_soup(self, styled=True):

        def _recur_unit(unit):
            if not len(unit.children) or unit.key == unit.children[0].key:
                text = unit.read_contents()
                if styled:
                    # This inlines external style sheets
                    premailer = Premailer(text,
                                          base_url=self.rendered_package_path,
                                          disable_link_rewrites=True)
                    text = premailer.transform()
                soup = BeautifulSoup(text, features='html5lib')
                return soup
            soup = BeautifulSoup('', features='html5lib')
            for child in unit.children:
                child_soup = _recur_unit(child)
                bodies = child_soup.find_all('body')
                for body in bodies:
                    text = ''.join(x.encode('utf-8') for x in body.findChildren(recursive=False))
                    div = '<div>%s</div>' % text
                    div = BeautifulSoup(div, features='html.parser')
                    soup.body.append(div)
            return soup

        return _recur_unit(self.rendered_package)

    @Lazy
    def title(self):
        return self.context.label

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def filename(self):
        return self.identifier + '.html'

    @Lazy
    def content(self):
        html = self.content_soup().find('body').decode()
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

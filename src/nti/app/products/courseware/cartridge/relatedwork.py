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

from premailer import Premailer

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.contentfolder.resources import get_file_from_external_link
from nti.app.contentfolder.resources import is_internal_file_link

# TODO private method access
from nti.app.contenttypes.presentation.decorators.assets import _get_item_content_package
from nti.app.contenttypes.presentation.decorators.assets import _path_exists_in_package
from nti.app.contenttypes.presentation.decorators.assets import CONTENT_MIME_TYPE

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException, \
    CommonCartridgeExportExceptionBundle

from nti.app.products.courseware.cartridge.interfaces import ICanvasWikiContent, IIMSResource
from nti.app.products.courseware.cartridge.interfaces import ICartridgeWebContent
from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit
from nti.app.products.courseware.cartridge.interfaces import IIMSWebLink

from nti.app.products.courseware.cartridge.renderer import execute
from nti.app.products.courseware.cartridge.renderer import get_renderer

from nti.app.products.courseware.cartridge.web_content import AbstractIMSWebContent, S3WebContent
from nti.app.products.courseware.cartridge.web_content import IMSWebContent

from nti.app.products.courseware.qti.utils import update_external_resources, is_internal_resource, is_s3

from nti.common import random

from nti.contentlibrary.interfaces import IContentPackage

from nti.contentlibrary_rendering.interfaces import IContentPackageRenderMetadata

from nti.ntiids.ntiids import find_object_with_ntiid, is_valid_ntiid_string

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
        if is_internal_file_link(self.context.href):
            resource = get_file_from_external_link(self.context.href)
            resource.seek(0)
            target_path = os.path.join(path, self.filename)
            self.copy_file_resource(resource, target_path)
        else:
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
            if root is not None:
                source_path = os.path.join(root.absolute_path, self.context.href)
                target_path = os.path.join(path, self.filename)
                self.copy_resource(source_path, target_path)
            else:
                logger.warning(u"Unable to locate a content package for %s" % self.context.label)
                raise CommonCartridgeExportException(u"Unable to locate a content package for %s" % self.context.label)


def get_param_value(bs_param):
    return bs_param.attrs.get('value')


class EmbedWidget(object):

    def source(self, bs_iframe, bs_param):
        source = get_param_value(bs_param)
        bs_iframe.attrs['src'] = source

    def width(self, bs_iframe, bs_param):
        width = get_param_value(bs_param) or '100%'
        bs_iframe.attrs['width'] = width

    def height(self, bs_iframe, bs_param):
        height = get_param_value(bs_param) or '300'
        bs_iframe.attrs['height'] = height

    def __call__(self, bs_obj):
        soup_factory = BeautifulSoup('', 'html.parser')  # There should be a better way to do this
        iframe = soup_factory.new_tag('iframe')
        params = bs_obj.find_all('param')
        for param in params:
            name = param.attrs['name']
            foo = getattr(self, name, None)
            if foo is not None:
                foo(iframe, param)
        bs_obj.replace_with(iframe)
        return []


def image_collection(bs_obj):
    pass


def nti_card(bs_obj):
    deps = []
    soup_factory = BeautifulSoup('', 'html.parser')  # There should be a better way to do this
    ntiid = bs_obj.find('param', {'name': 'ntiid'})
    ntiid = get_param_value(ntiid)
    card = find_object_with_ntiid(ntiid)
    if card is None:
        raise CommonCartridgeExportException(u'Unable to resolve NTICard NTIID %s' % ntiid)
    content_package = card.__parent__
    href = bs_obj.find('param', {'name': 'href'})
    href = get_param_value(href)
    if is_valid_ntiid_string(href):
        raise CommonCartridgeExportException(u'NTI Card with ntiid href %s' % href)
    elif is_internal_resource(href):
        from IPython.terminal.debugger import set_trace;set_trace()

        deps.append(IMSWebContent(content_package, href))
        if href.startswith('/'):
            href = href[1:]
        href = os.path.join('$IMS-CC-FILEBASE$', 'dependencies', href)
    elif is_s3(href):
        file_hash = random.generate_random_string(4)
        deps.append(S3WebContent(href, file_hash))
        path = urllib_parse.urlparse(href).path[1:]
        filename = os.path.basename(path)
        filename = '%s_%s' % (file_hash, filename)
        href = os.path.join('$IMS-CC-FILEBASE$', 'dependencies', filename)

    description = bs_obj.find('span', {'class': 'description'})
    description = description.string
    title = bs_obj.find('param', {'name': 'title'})
    title = get_param_value(title)
    creator = bs_obj.find('param', {'name': 'creator'})
    creator = get_param_value(creator)

    anchor = soup_factory.new_tag('a')
    anchor.attrs['href'] = href
    anchor.attrs['style'] = 'text-decoration: none;'

    div = soup_factory.new_tag('div')
    div.attrs['style'] = 'background: #fafdff; border: 1px solid #e3f2fc; height: 102px; width: 100%'
    anchor.append(div)

    inner_div = soup_factory.new_tag('div')
    inner_div.attrs['style'] = 'padding: 10px 45px 10px 0;margin-left: 15px;'
    div.append(inner_div)

    title_div = soup_factory.new_tag('div')
    title_div.string = title
    title_div.attrs['style'] = 'overflow:  hidden; text-overflow: ellipsis; margin-bottom: 5px; color: #494949; font: normal 600 15px/20px "Open Sans", sans-serif;'
    inner_div.append(title_div)

    byline_div = soup_factory.new_tag('div')
    byline_div.string = 'By %s' % creator
    byline_div.attrs['style'] = 'font: normal 600 10px/10px "Open Sans", sans-serif; text-transform: uppercase; color: #3fb3f6; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'
    inner_div.append(byline_div)

    desc_div = soup_factory.new_tag('div')
    desc_div.string = description
    desc_div.attrs['style'] = 'overflow: hidden; text-overflow: ellipsis; color: #494949; font: normal normal 12px/1rem "Open Sans", sans-serif; margin-top: 5px; max-height: 2rem;'
    inner_div.append(desc_div)

    bs_obj.replace_with(anchor)
    return deps


def nti_video_roll(bs_obj):
    # We will need recursive dependencies for this
    raise CommonCartridgeExportException(u'NTI Video Roll')
    # ntiid = bs_obj.attrs['data-ntiid']
    # video_roll = find_object_with_ntiid(ntiid)
    # if video_roll is None:
    #     raise CommonCartridgeExportException(u'Unable to resolve NTI Video Roll %s' % ntiid)
    # return [IIMSWebContentUnit(video_roll)]


def nti_video(bs_obj):
    soup_factory = BeautifulSoup('', 'html.parser')
    iframe = soup_factory.new_tag('iframe')
    ntiid = bs_obj.attrs['data-ntiid']
    video = find_object_with_ntiid(ntiid)
    if video is None:
        raise CommonCartridgeExportException(u'Unable to resolve NTI Video %s' % ntiid)
    ims_video = IIMSResource(video)
    iframe.attrs['src'] = os.path.join('$IMS-CC-FILEBASE$', 'dependencies', ims_video.filename)
    iframe.attrs['width'] = ims_video.width + 20
    iframe.attrs['height'] = ims_video.height + 20
    bs_obj.replace_with(iframe)
    return [ims_video]


def nti_timeline(bs_obj):
    raise CommonCartridgeExportException(u'NTI Timeline %s' % bs_obj)


# Maps mime_types to an export callable
# XXX: If you use a class here, you must be careful not to be stateful, as
# the same instance will be used to handle these
SUPPORTED_RENDERED_EXPORTS = {
    'application/vnd.nextthought.content.embeded.widget': EmbedWidget(),
    'application/vnd.nextthought.image-collection': image_collection,
    'application/vnd.nextthought.nticard': nti_card,
    'application/vnd.nextthought.videoroll': nti_video_roll,
    'application/vnd.nextthought.ntivideo': nti_video,
    'application/vnd.nextthought.ntitimeline': nti_timeline,
    'application/vnd.nextthought.videosource': lambda x: [],  # no-op
    'application/vnd.nextthought.mediatranscript': lambda x: []  # no-op
}


def external_export_rendered_content(html):
    errors = []
    dependencies = []
    soup = BeautifulSoup(html, features='html.parser')
    objects = soup.find_all('object')
    for obj in objects:
        mimetype = obj.attrs.get('type')
        foo = SUPPORTED_RENDERED_EXPORTS.get(mimetype)
        if foo is None:
            errors.append(CommonCartridgeExportException(u'Unsupported rendered content type: %s' % mimetype))
            continue
        try:
            dependencies.extend(foo(obj))
        except CommonCartridgeExportException as e:
            errors.append(e)
    return soup.decode(), dependencies, errors


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
            metadata_job = metadata.mostRecentRenderJob()
            if not metadata_job or not metadata_job.is_success():
                raise CommonCartridgeExportException(u'Related work ref %s failed to render.' % self.title)
        if rendered_package is None:
            raise CommonCartridgeExportException(u'Unable to find content package for related work ref %s.' % self.title)
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
        html, dependencies = update_external_resources(self.context, html)
        self.dependencies['dependencies'].extend(dependencies)
        # XXX order matters. We could consider adding a class onto elements that have already been parsed to make these
        # idempotent
        html, dependencies, errors = external_export_rendered_content(html)
        if len(errors) > 0:
            raise CommonCartridgeExportExceptionBundle(errors)
        self.dependencies['dependencies'].extend(dependencies)
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

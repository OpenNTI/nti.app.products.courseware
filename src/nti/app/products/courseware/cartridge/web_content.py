#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

import os
import requests
import shutil

from collections import defaultdict

from pyramid.threadlocal import get_current_request

from requests import HTTPError

from six.moves import urllib_parse

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.intid import IIntIds

from zope.schema.fieldproperty import createFieldProperties

from nti.app.contenttypes.presentation.decorators.assets import _get_item_content_package
from nti.app.contenttypes.presentation.decorators.assets import _path_exists_in_package

from nti.app.products.courseware.cartridge.exceptions import CommonCartridgeExportException

from nti.app.products.courseware.cartridge.interfaces import IIMSWebContentUnit

from nti.appserver.httpexceptions import HTTPException

from nti.contentlibrary.interfaces import IContentPackage

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.traversal.traversal import find_interface

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class WebContentMixin(object):

    def create_dirname(self, path):
        dirname = os.path.dirname(path)
        if not os.path.exists(dirname):
            os.makedirs(dirname)

    def copy_file_resource(self, src_object, target_path):
        self.create_dirname(target_path)
        with open(target_path, 'w') as dest:
            shutil.copyfileobj(src_object, dest)
            return True

    def copy_resource(self, source_path, target_path):
        if os.path.exists(source_path):
            self.create_dirname(target_path)
            shutil.copy(source_path, target_path)
            return True
        else:
            raise CommonCartridgeExportException(u'Source Path %s does not exist' % source_path)

    def write_resource(self, path, resource):
        self.create_dirname(path)
        with open(path, 'w') as fd:
            fd.write(resource.encode('utf-8'))
        return True

    def external_resource(self, target_path, response):
        self.create_dirname(target_path)
        with open(target_path, 'w') as fd:
            for block in response.iter_content(1024):
                fd.write(block)

    @Lazy
    def intids(self):
        intids = component.getUtility(IIntIds)
        return intids

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier


@interface.implementer(IIMSWebContentUnit)
class AbstractIMSWebContent(WebContentMixin):

    createFieldProperties(IIMSWebContentUnit)

    def __init__(self, context):
        self.context = context
        self.dependencies = defaultdict(list)

    def export(self, dirname):
        raise NotImplementedError


@interface.implementer(IIMSWebContentUnit)
class IMSWebContent(AbstractIMSWebContent):
    """
    Wrapper class for rendered content files that are not associated with an object
    """

    def __init__(self, context, path_to):
        super(IMSWebContent, self).__init__(context)
        self.path_to = path_to

    @Lazy
    def identifier(self):
        intids = component.getUtility(IIntIds)
        intid = intids.register(self)
        # Start at A
        identifier = u''.join([chr(65 + int(i)) for i in str(intid)])
        return unicode(identifier)
    __name__ = identifier

    @Lazy
    def content_package(self):
        package = find_interface(self.context, IContentPackage, strict=False)
        if package is None and getattr(self.context, 'target', False):
            target = find_object_with_ntiid(self.context.target)
            package = find_interface(target, IContentPackage, strict=False)
        if package is None:
            # ok lets try the hammer...
            for name in ('href', 'icon'):
                value = getattr(self.context, name, None)
                if value and not value.startswith('/') and '://' not in value:
                    if     package is None \
                        or not _path_exists_in_package(value, package):
                        # We make sure each url is in the correct package.
                        package = _get_item_content_package(self.context, value)
        if not package:
            raise CommonCartridgeExportException(u'Unable to locate a content package for %s' % self.context)
        return package

    @Lazy
    def filename(self):
        if self.path_to.startswith('/'):
            return self.path_to[1:]
        return self.path_to

    @Lazy
    def content_directory(self):
        root = getattr(self.content_package, 'root', None)
        if root is None:
            raise CommonCartridgeExportException(u'Corrupt content package %s' % self.content_package)
        return root.absolute_path

    def export(self, dirname):
        if self.path_to.startswith('/'):
            # We have an absolute URL, lets make a subrequest to retrieve
            request = get_current_request()
            subrequest = request.blank(self.path_to, base_url=request.application_url)
            subrequest.method = 'GET'
            subrequest.possible_site_names = request.possible_site_names
            # prepare environ
            repoze_identity = request.environ['repoze.who.identity']
            subrequest.environ['REMOTE_USER'] = request.environ['REMOTE_USER']
            subrequest.environ['repoze.who.identity'] = repoze_identity.copy()
            for k in request.environ:
                if k.startswith('paste.') or k.startswith('HTTP_'):
                    if k not in subrequest.environ:
                        subrequest.environ[k] = request.environ[k]
            try:
                response = request.invoke_subrequest(subrequest)
            except HTTPException:
                raise CommonCartridgeExportException(u'Unable to retrieve %s via subrequest' % self.path_to)
            target_path = os.path.join(dirname, self.path_to[1:])  # Remove leading slash
            self.external_resource(target_path, response)
        else:
            source_path = os.path.join(self.content_directory, self.path_to)
            target_path = os.path.join(dirname, self.path_to)
            self.copy_resource(source_path, target_path)


class S3WebContent(WebContentMixin):

    createFieldProperties(IIMSWebContentUnit)

    def __init__(self, s3_url, file_hash):
        self.s3_url = s3_url
        self.file_hash = file_hash

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
        return urllib_parse.urlparse(self.s3_url).path[1:]  # Remove starting slash

    @Lazy
    def filename(self):
        # We add a hash in front here because these may be in mulitple content pacakges
        # When this happens we get into a situation where multiple ids point to the same file
        # because it's name is the same. Rather than adding the entire id we do random so the name is
        # still easy to read
        filename = os.path.basename(self.href)
        filename = '%s_%s' % (self.file_hash, filename)
        return filename

    def export(self, dirname):
        target_path = os.path.join(dirname, self.filename)
        response = requests.get(self.s3_url, stream=True)
        try:
            response.raise_for_status()
        except HTTPError:
            raise CommonCartridgeExportException(u'Unable to export resource with response: %s' % response)
        self.external_resource(target_path, response)
        return True

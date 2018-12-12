#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy
import csv
import subprocess

from argparse import ArgumentParser

UA_STRING = 'NextThought Bulk Migration Utility'


def _parse_args():
    arg_parser = ArgumentParser(description=UA_STRING)
    arg_parser.add_argument('-m', '--migrator', dest='migrator',
                            help='Migration script')
    arg_parser.add_argument('-f', '--file', dest='csv',
                            help="CSV file of catalog entry NTIIDs")
    arg_parser.add_argument('-s', '--source-server', dest='source',
                            help="Source server (https://janux.ou.edu, etc).")
    arg_parser.add_argument('-d', '--dest-server', dest='dest',
                            help="Destination server (https://canvas.ou.edu, etc).")
    arg_parser.add_argument('-u', '--username', dest='username',
                            help="User to authenticate with the server.")
    arg_parser.add_argument('-p', '--password', dest='password',
                            help="User to authenticate password")
    arg_parser.add_argument('-k' '--key', dest='access_token',
                            help="Canvas Developer Key.")

    return arg_parser.parse_args()


def main():
    # XXX: This is OSX specific
    args = _parse_args()

    sub_args = '-s %s -d %s -u %s -p %s -k %s' % (args.source,
                                                  args.dest,
                                                  args.username,
                                                  args.password,
                                                  args.access_token)
    # TODO finish
    with open(args.csv, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            migrate_args = copy.copy(args.__dict__)
            migrate_args['ntiid'] = row[0]
            subprocess.call(['python', args.migrator, ])


if __name__ == '__main__':
    main()

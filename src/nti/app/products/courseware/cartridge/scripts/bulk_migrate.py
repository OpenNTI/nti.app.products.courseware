#!/usr/bin/env python
# -*- coding: utf-8 -*-
import copy
import csv
import os
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
    arg_parser.add_argument('-o', '--output', dest='output',
                            help='The output destination file')

    return arg_parser.parse_args()


def main():
    args = _parse_args()

    sub_args = '-s %s -d %s -u %s -p %s -k %s' % (args.source,
                                                  args.dest,
                                                  args.username,
                                                  args.password,
                                                  args.access_token)
    FNULL = open(os.devnull, 'w')
    processes = []
    with open(args.csv, 'rb') as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            new_args = sub_args + ' -n %s' % row[0]
            call_list = ['python', args.migrator]
            call_list.extend(new_args.split(' '))
            f = os.tmpfile()
            p = subprocess.Popen(call_list, stdout=f, stderr=FNULL)
            processes.append((p, f))
    num = 1
    with open(args.output, 'w') as result:
        for p, f in processes:
            p.wait()
            print "Process %s of %s completed" % (num, len(processes))
            num += 1
            f.seek(0)
            result.write(f.read())
            result.write('\n\n')
            f.close()
    FNULL.close()


if __name__ == '__main__':
    main()

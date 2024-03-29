#!/usr/bin/env python
# Copyright (c) 2015 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Tool for interacting with Buildbucket.

Usage:
  $ depot-tools-auth login https://cr-buildbucket.appspot.com
  $ buildbucket.py \
    put \
    --bucket master.tryserver.chromium.linux \
    --builder my-builder \

  Puts a build into buildbucket for my-builder on tryserver.chromium.linux.
"""

from __future__ import print_function

import argparse
import json
import urlparse
import os
import sys

from third_party import httplib2

import auth


BUILDBUCKET_URL = 'https://cr-buildbucket.appspot.com'
BUILDBUCKET_API_URL = urlparse.urljoin(
  BUILDBUCKET_URL,
  '_ah/api/buildbucket/v1/builds',
)


def add_common_arguments(parser):
  parser.add_argument(
    '--response-json',
    help=(
      'A path to which the response JSON will be written. '
      'If no valid JSON is received, nothing will be written.'
    )
  )


def main(argv):
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v',
    '--verbose',
    action='store_true',
  )
  subparsers = parser.add_subparsers(dest='command')

  get_parser = subparsers.add_parser('get')
  add_common_arguments(get_parser)
  get_parser.add_argument(
    '--id',
    help='The ID of the build to get the status of.',
    required=True,
  )

  put_parser = subparsers.add_parser('put')
  add_common_arguments(put_parser)
  put_parser.add_argument(
    '-b',
    '--bucket',
    help=(
      'The bucket to schedule the build on. Typically the master name, e.g.'
      ' master.tryserver.chromium.linux.'
    ),
    required=True,
  )
  put_parser.add_argument(
    '-c',
    '--changes',
    help='A flie to load a JSON list of changes dicts from.',
  )
  put_parser.add_argument(
    '-n',
    '--builder-name',
    help='The builder to schedule the build on.',
    required=True,
  )
  put_parser.add_argument(
    '-p',
    '--properties',
    help=(
      'A file to load a JSON dict of properties from. Use "-" to pipe JSON '
      'from another command.'
    ),
  )

  retry_parser = subparsers.add_parser('retry')
  add_common_arguments(retry_parser)
  retry_parser.add_argument(
    '--id',
    help='The ID of the build to retry.',
    required=True,
  )

  args = parser.parse_args()

  body = None

  if args.command == 'get':
    method = 'GET'
    url = '%s/%s' % (BUILDBUCKET_API_URL, args.id)
  elif args.command == 'put':
    changes = []
    if args.changes:
      try:
        with open(args.changes) as fp:
          changes.extend(json.load(fp))
      except (TypeError, ValueError):
        sys.stderr.write('%s contained invalid JSON list.\n' % args.changes)
        raise

    properties = {}
    if args.properties:
      try:
        # Allow using pipes to stream properties from another command, e.g.
        #   echo '{"foo": "bar", "baz": 42}' | buildbucket.py -p -
        if args.properties == '-':
          properties.update(json.load(sys.stdin))
        else:
          with open(args.properties) as fp:
            properties.update(json.load(fp))
      except (TypeError, ValueError):
        sys.stderr.write('%s contained invalid JSON dict.\n' % args.properties)
        raise

    body = json.dumps({
      'bucket': args.bucket,
      'parameters_json': json.dumps({
        'builder_name': args.builder_name,
        'changes': changes,
        'properties': properties,
      }),
    })
    method = 'PUT'
    url = BUILDBUCKET_API_URL
  elif args.command == 'retry':
    method = 'PUT'
    url = '%s/%s/retry' % (BUILDBUCKET_API_URL, args.id)

  authenticator = auth.get_authenticator_for_host(
    BUILDBUCKET_URL,
    auth.make_auth_config(use_oauth2=True),
  )
  http = authenticator.authorize(httplib2.Http())
  http.force_exception_to_status_code = True

  if args.verbose:
    print('Request URL:', url)
    print('Request method:', method)
    print('Request body:', body)

  response, content = http.request(
    url,
    method,
    body=body,
    headers={'Content-Type': 'application/json'},
  )

  if args.verbose:
    print('Response:', response)
    print('Content:', content)

  try:
    content_json = json.loads(content)
    if args.response_json:
      with open(args.response_json, 'w') as response_json_file:
        response_json_file.write(content)
    build_url = content_json['build']['url']
  except (ValueError, TypeError, KeyError):
    pass
  else:
    print('Build: %s' % build_url)

  return response.status != 200


if __name__ == '__main__':
  sys.exit(main(sys.argv))

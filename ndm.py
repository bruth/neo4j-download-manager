#! /usr/bin/env python

from __future__ import print_function, absolute_import, unicode_literals
import os
import re
import sys
import json
import urllib2
from argparse import ArgumentParser, RawDescriptionHelpFormatter, PARSER


__author__ = 'Byron Ruth'
__version__ = '0.1.0b'


DEFAULT_NDM_HOME = os.path.join(os.path.expanduser('~'), '.ndm')
NEO4J_DOWNLOAD_URL = 'http://dist.neo4j.org/neo4j-community-{}-unix.tar.gz'

# Get the NDM_HOME environment variable or use the default one
NDM_HOME = os.environ.get('NDM_HOME', DEFAULT_NDM_HOME)

# Default directory for named environments
NDM_ENVS = os.path.join(NDM_HOME, 'envs')

# Directory containing the downloaded releases
NDM_CACHE = os.path.join(NDM_HOME, 'cache')

NEO4J_TAGS_URL = 'https://api.github.com/repos/neo4j/neo4j/tags'


def cli(*args, **kwargs):
    "Decorates a function and converts it into an ArgumentParser instance."
    def decorator(func):
        class Parser(ArgumentParser):
            def handle(self, *args, **kwargs):
                try:
                    func(*args, **kwargs)
                except Exception, e:
                    self.error(e.message)

            # No catching of exceptions for debugging
            def handle_raw(self, *args, **kwargs):
                func(*args, **kwargs)

        return Parser(*args, **kwargs)
    return decorator


# Regexp to match on tags that are in the 'stable' format
stable_tag = re.compile(r'^\d+\.\d+(\.\d+)?$')


def cmp_semver(x, y):
    "Compare function for semantic version strings."
    return cmp([int(t) for t in x.split('.')], [int(t) for t in y.split('.')])


# Cache in case these are used multiple times in a command. This prevents
# redundant API requests.
release_versions = None


def _release_versions():
    global release_versions
    if not release_versions:
        resp = urllib2.urlopen(NEO4J_TAGS_URL)
        tags = [t['name'] for t in json.load(resp)]
        stable = filter(lambda x: stable_tag.match(x), tags)
        release_versions = tuple(sorted(stable, cmp=cmp_semver, reverse=True))
    return list(release_versions)


def group_release_versions(versions):
    key = None
    group = None
    groups = []

    for version in versions:
        points = version.split('.')
        if points[:2] != key:
            key = points[:2]
            group = []
            groups.append(group)
        group.append(version)
    return groups


def check_release_exists(version):
    """Performs a HEAD request to check whether a particular release is
    available for download.
    """
    url = NEO4J_DOWNLOAD_URL.format(version)
    request = urllib2.Request(url)
    request.get_method = lambda: 'HEAD'

    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError:
        return False
    return response.getcode() == 200


def download_release(version):
    url = NEO4J_DOWNLOAD_URL.format(version)
    filename = os.path.basename(url)
    request = urllib2.Request(url)

    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError:
        return False

    with open(os.path.join(NDM_CACHE, filename), 'wb') as fh:
        for chunk in response:
            fh.write(chunk)

    return True


@cli(description='Lists the stable release versions of Neo4j')
def releases(options):
    "Returns a sorted list of stable release versions."
    versions = _release_versions()
    if options.list:
        print('\n'.join(versions))
    else:
        groups = group_release_versions(versions)
        print('\n'.join([', '.join(group) for group in groups]))

releases.add_argument('-l', '--list', action='store_true',
                      help='Print a flat list instead of groups')


# Top-level commands
commands = {
    'releases': releases,
}


def create_parser():
    # http://stackoverflow.com/q/13423540/407954
    class SubcommandHelpFormatter(RawDescriptionHelpFormatter):
        def _format_action(self, action):
            parts = super(RawDescriptionHelpFormatter, self)\
                ._format_action(action)
            if action.nargs == PARSER:
                parts = '\n'.join(parts.split('\n')[1:])
            return parts

    # Top-level argument parser
    parser = ArgumentParser(description='Neo4j Download Manager (NDM)',
                            version='ndm v{0}'.format(__version__),
                            epilog="See '%(prog)s <command> --help' for more "
                                   "information on a specific command.",
                            formatter_class=SubcommandHelpFormatter)

    parser.add_argument('--debug', action='store_true', help='debug mode')

    # Add sub-parsers for each command
    subparsers = parser.add_subparsers(title='available commands',
                                       dest='command',
                                       metavar='<command>')

    # Populate subparsers
    for key in commands:
        _parser = commands[key]
        # Add it by name
        subparser = subparsers.add_parser(key, add_help=False,
                                          help=_parser.description)
        # Update subparser with properties of subparser. Keep
        # track of the generated `prog` since it is relative to
        # the top-level command
        prog = subparser.prog
        subparser.__dict__.update(_parser.__dict__)
        subparser.prog = prog

    return parser


if __name__ == '__main__':
    parser = create_parser()
    args = sys.argv[1:]
    if not args:
        args.append('--help')
    options = parser.parse_args(args)

    if options.debug:
        handler = commands[options.command].handle_raw
    else:
        handler = commands[options.command].handle

    handler(options)

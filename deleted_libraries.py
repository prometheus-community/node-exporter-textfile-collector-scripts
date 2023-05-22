#!/usr/bin/env python3
"""
Script to count the number of deleted libraries that are linked by running
processes and expose a summary as Prometheus metrics.

The aim is to discover processes that are still using libraries that have since
been updated, perhaps due security vulnerabilities.
"""

import errno
import glob
import os
import sys
from prometheus_client import CollectorRegistry, Gauge, generate_latest


def main():
    processes_linking_deleted_libraries = {}

    for path in glob.glob('/proc/*/maps'):
        try:
            with open(path, 'rb') as file:
                for line in file:
                    part = line.decode().strip().split()

                    if len(part) == 7:
                        library = part[5]
                        comment = part[6]

                        if '/lib/' in library and '(deleted)' in comment:
                            if path not in processes_linking_deleted_libraries:
                                processes_linking_deleted_libraries[path] = {}

                                if library in processes_linking_deleted_libraries[path]:
                                    processes_linking_deleted_libraries[path][library] += 1
                                else:
                                    processes_linking_deleted_libraries[path][library] = 1
        except EnvironmentError as e:
            # Ignore non-existent files, since the files may have changed since
            # we globbed.
            if e.errno != errno.ENOENT:
                sys.exit('Failed to open file: {0}'.format(path))

    num_processes_per_library = {}

    for process, library_count in processes_linking_deleted_libraries.items():
        libraries_seen = set()
        for library, count in library_count.items():
            if library in libraries_seen:
                continue

            libraries_seen.add(library)
            if library in num_processes_per_library:
                num_processes_per_library[library] += 1
            else:
                num_processes_per_library[library] = 1

    registry = CollectorRegistry()
    g = Gauge('node_processes_linking_deleted_libraries',
              'Count of running processes that link a deleted library',
              ['library_path', 'library_name'], registry=registry)

    for library, count in num_processes_per_library.items():
        dir_path, basename = os.path.split(library)
        g.labels(dir_path, basename).set(count)

    print(generate_latest(registry).decode(), end='')


if __name__ == "__main__":
    main()

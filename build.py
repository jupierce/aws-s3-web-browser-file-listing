#!/usr/bin/env python3

# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import pathlib
import itertools

build_file_path = pathlib.Path(__file__).absolute()
repo_root_path = build_file_path.parent
dist_dir_path = repo_root_path.joinpath('dist')
output_template_path = dist_dir_path.joinpath('aws-s3-browser-file-listing.cf.yaml')


# Inlines lambda file contents into the Cloud Formation template file and outputs
# the result into a viable final template.
# This process is used so that lambdas can be more easily maintained as independent files.
def render_template() -> str:
    src_path = repo_root_path.joinpath('src')
    template_file_path = src_path.joinpath('aws-s3-browser-file-listing.cf-template.yaml')
    output = ''

    with template_file_path.open(mode='r') as f:
        for line in f.readlines():
            if line.strip().startswith('INJECT'):
                padding = line.split('I')[0]  # whitespace to the left of INJECT
                filename = line.strip().split(' ')[-1]  # filename to inject
                target_file_path = src_path.joinpath(filename)
                with target_file_path.open(mode='r') as incoming:
                    for incoming_line in incoming.readlines():
                        inject_line = padding + incoming_line
                        output += inject_line
            else:
                output += line

    return output


def render_template_to_dist():
    dist_dir_path.mkdir(exist_ok=True)
    rendered_template = render_template()
    output_template_path.write_text(rendered_template)
    print(f'Rendered: {str(output_template_path)}')


def test_is_render_up_to_date():
    if not output_template_path.is_file():
        raise IOError(f'{str(output_template_path)} does not exist. Run build.py to populate it.')

    file_lines = output_template_path.read_text().strip().split()
    desired_lines = render_template().strip().split()
    for line_tuple in itertools.zip_longest(file_lines, desired_lines):
        if line_tuple[0] != line_tuple[1]:
            raise IOError(f'{str(output_template_path)} is not up-to-date. Run build.py to update it.')


if __name__ == '__main__':
    render_template_to_dist()

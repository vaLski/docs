#!/usr/bin/env python3

from brigit import Git
import os
import sys
import subprocess

arg_len = len(sys.argv)
if arg_len <= 1:
    print("Usage: tgv filter_arg\n")
    sys.exit(1)
else:
    filter_arg = sys.argv[1]

if 'COCKROACH_DOCS_REPO' in os.environ:
    docs_dir = os.environ['COCKROACH_DOCS_REPO']
else:
    docs_dir = os.path.join(os.environ['HOME'],
                            'go/src/github.com/cockroachdb/docs')

if 'COCKROACH_CODE_REPO' in os.environ:
    code_dir = os.environ['COCKROACH_CODE_REPO']
else:
    code_dir = os.path.join(os.environ['HOME'],
                            'go/src/github.com/cockroachdb/cockroach')

docs_repo = Git(docs_dir)
code_repo = Git(code_dir)

code_repo.pull()

os.chdir(code_dir)
make_args = ['make', 'bin/.docgen_bnfs']
subprocess.check_call(make_args)

os.chdir(docs_dir)    # or wherever, as long as it isn't the CRDB repo

docgen_args = [
    'docgen', 'grammar', 'svg',
    '{code_dir}/docs/generated/sql/bnf/'.format(code_dir=code_dir),
    '{docs_dir}/_includes/sql/v2.0/diagrams/'.format(docs_dir=docs_dir),
    '--filter={filter}'.format(filter=filter_arg)
]

subprocess.check_call(docgen_args)

#!/bin/sh
set -eu
git config core.hooksPath .githooks
printf '%s\n' 'local repository policy hooks enabled'

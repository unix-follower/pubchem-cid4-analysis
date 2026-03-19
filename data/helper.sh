#!/usr/bin/env bash

set -e

make_graph() {
  dot -Tsvg -o cid_4.svg cid_4.dot
}

make_graph

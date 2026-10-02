#!/bin/bash

# Author: Nick Galtry
# Usage: Script that jq queries against JSON output of multipathd show multipaths command, formats results for Promtheus textfile collector
# Requires: jq

set -e

# Function for handling errors, "scrubs the multipathd.prom file"
error_trap() {
    local error_msg="$1"
    echo "$error_msg"
    exit 1
}

if ! command -v jq &> /dev/null; then
  error_trap "Error: jq is not installed."
fi

# Variable set for command to run with jq
if ! command_output=$(multipathd show multipaths json)
then
  error_trap "Error: Failed to run multipathd show multipaths"
fi

if echo "$command_output" | jq -e '.maps | length == 0' >/dev/null 2>/dev/null; then
  exit 0
fi

node_multipath_paths_dm_st=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: [.path_groups[].paths[] | select(.dm_st == "active")] | length
        }' |
        sed -E 's/^/node_multipath_paths_dm_st/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod":"([^"]*)"/prod:"\1",state="active"/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g'
)

if [ -z "$node_multipath_paths_dm_st" ]; then
 error_trap "Error processing node_multipath_paths_dm_st metric"
else
 echo "# HELP node_multipath_paths_dm_st A count of paths with active state in path_groups"
 echo "# TYPE node_multipath_paths_dm_st gauge"
 echo "${node_multipath_paths_dm_st}"
fi

node_multipath_paths_chk_st=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: [.path_groups[].paths[] | select(.chk_st == "ready")] | length
        }' |
        sed -E 's/^/node_multipath_paths_chk_st/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod":"([^"]*)"/prod:"\1",state="ready"/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g'
)

if [ -z "$node_multipath_paths_chk_st" ]; then
 error_trap "Error processing node_multipath_paths_chk_st metric"
else
 echo "# HELP node_multipath_paths_chk_st A count of paths with chk_st ready in path_groups"
 echo "# TYPE node_multipath_paths_chk_st gauge"
 echo "${node_multipath_paths_chk_st}"
fi

node_multipath_paths_dev_st=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: [.path_groups[].paths[] | select(.dev_st == "running")] | length
        }' |
        sed -E 's/^/node_multipath_paths_dev_st/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod":"([^"]*)"/prod:"\1",state="running"/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g'
)
if [ -z "$node_multipath_paths_dev_st" ]; then
 error_trap "Error processing node_multipath_paths_dev_st metric"
else
 echo "# HELP node_multipath_paths_dev_st A count of paths with dev_st running in path_groups"
 echo "# TYPE node_multipath_paths_dev_st gauge"
 echo "${node_multipath_paths_dev_st}"
fi

node_multipath_dm_st=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: [select(.dm_st == "active")] | length
        }' |
        sed -E 's/^/node_multipath_dm_st/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod":"([^"]*)"/prod:"\1",state="active"/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g'
)
if [ -z "$node_multipath_dm_st" ]; then
 error_trap "Error processing node_multipath_dm_st metric"
else
 echo "# HELP node_multipath_dm_st A count of active dm_st per multipath device"
 echo "# TYPE node_multipath_dm_st gauge"
 echo "${node_multipath_dm_st}"
fi

node_multipath_path_nr=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: .paths
        }' |
        sed -E 's/^/node_multipath_path_nr/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod"/prod/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g' |
        sed 's/ "count"://'
)
if [ -z "$node_multipath_path_nr" ]; then
 error_trap "Error processing node_multipath_path_nr metric"
else
 echo "# HELP node_multipath_path_nr A count of paths per multipath device"
 echo "# TYPE node_multipath_path_nr gauge"
 echo "${node_multipath_path_nr}"
fi

node_multipath_path_faults=$(echo "$command_output" |
    jq -c -r '.maps[] |
        {
         name: .name,
         uuid: .uuid,
         vend: (.vend | sub("^[[:space:]]+"; "") | sub("[[:space:]]+$"; "")),
         prod: .prod,
         count: .path_faults
        }' |
        sed -E 's/^/node_multipath_path_faults/;
                s/"name"/name/;
                s/"uuid"/uuid/;
                s/"vend"/vend/;
                s/"prod"/prod/;
                s/,"count":([0-9]+)}/\}\1/g;
                s/:/=/g' |
        sed 's/ "count"://'
)
if [ -z "$node_multipath_path_faults" ]; then
 error_trap "Error processing node_multipath_path_faults metric"
else
 echo "# HELP node_multipath_path_faults A count of faults reported per multipath device"
 echo "# TYPE node_multipath_path_faults gauge"
 echo "${node_multipath_path_faults}"
fi
#!/bin/bash
set -e
cd /opt/konfigurator/scripts
python3 -c "
import json
cfgs = json.load(open('tmp_2026-08-31_bpt_configs.json'))
for c in cfgs:
    print(c['tag'])
" > /tmp/bpt_tags.txt
while read -r tag; do
  cfg=$(python3 -c "
import json
cfgs = json.load(open('tmp_2026-08-31_bpt_configs.json'))
c = [x for x in cfgs if x['tag']=='$tag'][0]
json.dump(c, open('/tmp/bpt_cfg_$tag.json','w'))
")
  echo "=== $tag ==="
  node tmp_2026-08-31_bpt_run_vehicle.js /tmp/bpt_cfg_$tag.json /tmp/bpt_out_$tag > /tmp/bpt_log_$tag.txt 2>&1 && echo "OK $tag" || echo "FAIL $tag (see /tmp/bpt_log_$tag.txt)"
done < /tmp/bpt_tags.txt

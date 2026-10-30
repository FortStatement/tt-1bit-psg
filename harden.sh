#!/bin/sh
set -e
rm -rf /work/.harden && mkdir /work/.harden
cp -r /work/info.yaml /work/src /work/docs /work/.harden/
rm -f /work/.harden/src/user_config.json /work/.harden/src/config_merged.json
cd /work/.harden
ln -s /ttsetup/tt-support-tools tt
git init -q && git add -A && git -c user.name=local -c user.email=local commit -qm harden
tt_tool --create-user-config
tt_tool --harden --no-docker
tt_tool --print-stats || true
tt_tool --print-warnings || true
rm -rf /work/runs && mv runs /work/runs && cd / && rm -rf /work/.harden

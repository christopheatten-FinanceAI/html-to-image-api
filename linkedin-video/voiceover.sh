#!/usr/bin/env bash
# Adds a narration track to the rendered video. Needs ffmpeg and pico2wave (apt: libttspico-utils).
# Usage: ./voiceover.sh   -> writes fable-5.2-finance-linkedin-voiceover.mp4
set -euo pipefail
cd "$(dirname "$0")"
TMP=$(mktemp -d)
# start time (ms) | line
LINES=(
  "300|Claude Fable five point two is here."
  "2750|Same model as Mythos. Thirty percent faster. Externally tested."
  "7600|Twenty percent cheaper, and ahead on knowledge work benchmarks."
  "11400|Trading firms report record quant research scores, and fewer overstated answers."
  "16400|In governance, model risk becomes agent risk."
  "19500|Capability is not the bottleneck. Governance is."
)
TRIM="silenceremove=start_periods=1:start_threshold=-50dB,areverse,silenceremove=start_periods=1:start_threshold=-50dB,areverse"
inputs=(); filter=""; mix=""
for i in "${!LINES[@]}"; do
  at=${LINES[$i]%%|*}; text=${LINES[$i]#*|}
  pico2wave -l en-GB -w "$TMP/$i.wav" "<speed level=\"112\">$text</speed>" </dev/null
  inputs+=(-i "$TMP/$i.wav")
  filter+="[$((i+1)):a]$TRIM,adelay=$at:all=1[a$i];"; mix+="[a$i]"
done
filter+="${mix}amix=inputs=${#LINES[@]}:normalize=0,highpass=f=90,loudnorm=I=-16:TP=-1.5,apad[a]"
ffmpeg -nostdin -y -loglevel error -i fable-5.2-finance-linkedin.mp4 "${inputs[@]}" \
  -filter_complex "$filter" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 160k -ar 48000 \
  -shortest -movflags +faststart fable-5.2-finance-linkedin-voiceover.mp4
rm -rf "$TMP"
echo "wrote fable-5.2-finance-linkedin-voiceover.mp4"

#!/data/data/com.termux/files/usr/bin/bash
# Stop the Replay Studio services on Android. This does NOT end a YouTube broadcast (press Stop stream in
# the dashboard for that); a live session resumes into the same broadcast at the next termux-start.sh.
RUN="$HOME/replay-studio-data/run"
touch "$RUN/stopping"
for name in api worker; do
  [ -f "$RUN/$name.sup" ] && kill "$(cat "$RUN/$name.sup")" 2>/dev/null
  rm -f "$RUN/$name.sup"
done
pkill -f "replay-studio (api|worker)" 2>/dev/null
sleep 2
pkill -9 -f "replay-studio (api|worker)" 2>/dev/null
command -v termux-wake-unlock >/dev/null && termux-wake-unlock
echo "Replay Studio stopped."

set("log.stdout", true)
set("log.level", 3)

# ---------- music ----------
music = playlist(
  mode="random",
  reload_mode="watch",
  "/music"
)

def notify_track(m) =
  log("NOTIFY TRACK CALLED")

  title = m["title"]
  artist = m["artist"]
  filename = m["filename"]

  log("TRACK: #{artist} - #{title} (#{filename})")

  cmd = "curl --max-time 1 --connect-timeout 0.3 -s -X POST http://orchestrator:9000/event " ^
        "-H 'Content-Type: application/json' " ^
        "-d '{\"event\":\"track_started\",\"artist\":\"#{artist}\",\"title\":\"#{title}\",\"filename\":\"#{filename}\"}' " ^
        ">/dev/null 2>&1 &"

  ignore(system(cmd))
end

music = on_metadata(
  id="track_notify",
  music,
  notify_track
)

music = limit(music)

# ---------- jingles / TTS ----------
def next_jingle() =
  files = process.read.lines(
    "mkdir -p /jingles/playing; " ^
    "f=$(find /jingles/queued -maxdepth 1 -type f -name '*.wav' -readable | sort | head -n 1); " ^
    "if [ -n \"$f\" ]; then " ^
    "b=$(basename \"$f\"); " ^
    "dest=\"/jingles/playing/$b\"; " ^
    "mv \"$f\" \"$dest\" && printf '%s\n' \"$dest\"; " ^
    "fi"
  )

  files = list.filter(fun (x) -> x != "", files)

  if list.length(files) == 0 then
    null
  else
    jingle_file = list.hd(files)
    log("Play TTS jingle: #{jingle_file}")
    request.create(jingle_file)
  end
end

tts = request.dynamic(
  id="valera_tts",
  retry_delay=2.0,
  next_jingle
)

# ---------- final radio ----------
radio = fallback(
  track_sensitive=false,
  transitions=[fun(a,b) -> b, fun(a,b) -> b],
  [
    tts,
    music,
    blank()
  ]
)

radio = audio_to_stereo(radio)
radio = mksafe(radio)
radio = limit(radio)

output.icecast(
  %mp3(
    bitrate=128,
    samplerate=44100,
    stereo=true
  ),
  host="icecast",
  port=8000,
  password="source_pass",
  mount="gopfm.mp3",
  name="Gop-FM",
  description="Valera on the block",
  genre="Gop radio",
  radio
)
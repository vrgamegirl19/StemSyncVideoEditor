
import gradio as gr
import librosa
import numpy as np
import os
import tempfile
from moviepy.editor import VideoFileClip, concatenate_videoclips, AudioFileClip
from scipy.signal import medfilt
import shutil, tempfile, os
from moviepy.editor import vfx



DEBUG = True
def debug(msg):
    if DEBUG:
        print(msg)

def base(path):
    return os.path.splitext(os.path.basename(path))[0].lower()

def get_default_output_path():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(script_dir, "output")
    os.makedirs(out, exist_ok=True)
    i = 1
    while True:
        p = os.path.join(out, f"render_{i:03d}.mp4")
        if not os.path.exists(p):
            return p
        i += 1


# ======================================================
# intro / outro clips
# ======================================================        
def find_optional_clip(name):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(script_dir, name)
    return path if os.path.exists(path) else None

# ======================================================
# AUDIO ANALYSIS
# ======================================================
def analyze_audio(path):
    y, sr = librosa.load(path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    silence = np.percentile(rms, 10) * 1.5
    duration = librosa.get_duration(y=y, sr=sr)
    return {
        "y": y,
        "sr": sr,
        "rms": rms,
        "rms_times": rms_times,
        "silence": silence,
        "duration": duration
    }
# ======================================================
# stabilize_video
# ======================================================
def stabilize_video(path):
    return path

# ======================================================
# next beat after
# ======================================================
def next_beat_after(beats, t):
    for b in beats:
        if b >= t:
            return b
    return t

# ======================================================
# BEAT + ONSET SNAP
# ======================================================
def detect_snapped_beats(final_audio_path, snap_window):
    y, sr = librosa.load(final_audio_path, sr=None, mono=True)

    _, beats = librosa.beat.beat_track(y=y, sr=sr)
    beat_times = librosa.frames_to_time(beats, sr=sr)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    snapped = []
    for b in beat_times:
        nearest = min(onset_times, key=lambda o: abs(o - b)) if len(onset_times) else b
        if abs(nearest - b) <= snap_window:
            snapped.append(nearest)
        else:
            snapped.append(b)

    return sorted(set([float(t) for t in snapped]))

# ======================================================
# SECTION + PHRASE DETECTION
# ======================================================
def detect_sections(final_audio_path):
    y, sr = librosa.load(final_audio_path, sr=None, mono=True)
    rms = librosa.feature.rms(y=y)[0]
    rms = medfilt(rms, kernel_size=31)
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)

    thresh = np.percentile(rms, 70)
    sections = []
    current = None

    for t, e in zip(times, rms):
        label = "chorus" if e >= thresh else "verse"
        if current is None or current["type"] != label:
            current = {"start": t, "type": label}
            sections.append(current)

    for i in range(len(sections)):
        sections[i]["end"] = sections[i + 1]["start"] if i + 1 < len(sections) else times[-1]

    return sections

def section_at_time(sections, t):
    for s in sections:
        if s["start"] <= t < s["end"]:
            return s["type"]
    return "verse"

# ======================================================
# FreeClipCycler
# ======================================================
class FreeClipCycler:
    def __init__(self, clips):
        self.clips = clips
        self.idx = 0
        self.phase = 0  # 0 = normal, 1 = mirrored+reversed

    def next(self):
        clip = self.clips[self.idx]

        transform = []
        if self.phase == 1:
            transform = ["mirror", "reverse"]

        self.idx += 1
        if self.idx >= len(self.clips):
            self.idx = 0
            self.phase = (self.phase + 1) % 2

        return clip, transform

# ======================================================
# BEAT-LOCKED TIMELINE
# ======================================================
def generate_timeline(
    audio_files,
    video_files,
    beat_times,
    sections,
    cooldown,
    song_length,
    chorus_aggression,
    phrase_beats,
    downbeat_bias,
    free_cycler,
    free_clip_probability
):
    audio = {base(f.name): analyze_audio(f.name) for f in audio_files}
    video_map = {base(f.name): f.name for f in video_files}
    stems = [s for s in audio if s in video_map]

    if not stems:
        raise gr.Error("No matching audio/video stem names")

    vocal_stem = next((s for s in stems if "voc" in s or "vox" in s), None)

    timeline = []
    current = stems[0]
    last_used = {s: -999.0 for s in stems}
    last_cut_beat = -999

    for idx, t in enumerate(beat_times):
        if t >= song_length:
            break

        # Downbeat emphasis (favor every N beats)
        if downbeat_bias > 0 and idx % int(downbeat_bias) != 0:
            continue

        section = section_at_time(sections, t)

        # Chorus aggression: lower = more cuts
        min_beats = max(1, int(phrase_beats * (1 - chorus_aggression))) if section == "chorus" else phrase_beats

        if idx - last_cut_beat < min_beats:
            continue

        energy = {}
        active = []

        for s in stems:
            if t > audio[s]["duration"]:
                e = 0.0
            else:
                e = np.interp(t, audio[s]["rms_times"], audio[s]["rms"])
            energy[s] = e
            if e > audio[s]["silence"]:
                active.append(s)

        candidates = []
        for s in active:
            if s == current:
                continue
            if t - last_used[s] < cooldown:
                continue
            if s == vocal_stem and s not in active:
                continue
            candidates.append(s)

        if candidates:
            stem = max(candidates, key=lambda s: energy[s])
        elif len(active) == 0:
            stem = np.random.choice([s for s in stems if s != current])
        else:
            continue
        is_final_cut = (t >= song_length - 0.05)


        use_free = (
            free_cycler is not None
            and not is_final_cut
            and np.random.rand() < free_clip_probability
        )


        if use_free:
            clip_path, transform = free_cycler.next()
            timeline.append({
                "time": t,
                "type": "free",
                "clip": clip_path,
                "transform": transform,
                "beat_idx": idx,
                "section": section
            })
        else:
            timeline.append({
                "time": t,
                "type": "stem",
                "stem": stem,
                "beat_idx": idx,
                "section": section
            })


        last_used[stem] = t
        current = stem
        last_cut_beat = idx

    if not timeline or timeline[-1]["time"] < song_length:
        timeline.append({
            "time": song_length,
            "type": "stem",
            "stem": current,
            "beat_idx": len(beat_times),
            "section": section_at_time(sections, song_length)
        })

    return timeline, stems, video_map


def normalize_video(path, song_len, safe_start=0.05):
    path = stabilize_video(path)
    base = VideoFileClip(path, audio=False)

    if base.duration <= safe_start:
        raise RuntimeError(f"Video too short to use: {path}")

    if base.duration >= song_len + safe_start:
        # simple trim
        return base.subclip(safe_start, safe_start + song_len)

    # loop until long enough
    loops = int(np.ceil((song_len + safe_start) / base.duration))
    looped = concatenate_videoclips([base] * loops)

    return looped.subclip(safe_start, safe_start + song_len)


# ======================================================
# write_edit_summary
# ======================================================
import json

def write_edit_summary(timeline, output_path):
    summary = []

    for i in range(len(timeline) - 1):
        start = timeline[i]["time"]
        end = timeline[i + 1]["time"]

        summary.append({
            "clip": (
                os.path.basename(timeline[i]["clip"])
                if timeline[i].get("type") in ("free", "intro", "outro")
                else f"{timeline[i]['stem']}.mp4"
            ),

            "timeline_start": round(start, 3),
            "timeline_end": round(end, 3),
            "source_start": (
                0.0 if timeline[i].get("type") == "free"
                else round(start, 3)
            ),
            "duration": round(end - start, 3)
        })

    json_path = os.path.splitext(output_path)[0] + ".json"
    with open(json_path, "w") as f:
        json.dump(summary, f, indent=2)

    return json_path

# ======================================================
# VIDEO BUILD
# ======================================================
def build_video(timeline, stems, video_map, song_length, final_audio_path, output_path):
    SAFE_START = 0.05  # never allow frame-0 access

    videos = {
        s: normalize_video(video_map[s], song_length)
        for s in stems
    }

    segments = []
    start = 0.0
    free_clip_cache = {}

    # for e in timeline:
    #     end = e["time"]
    #     if end <= start:
    #         continue
    for e in timeline:
        end = e.get("end", e["time"])

        # allow intro/outro at same timestamp as start
        if e.get("type") not in ("intro", "outro") and end <= start:
            continue


        # 🔒 critical clamp
        clip_start = max(start, SAFE_START)
        clip_end = max(end, clip_start + 0.001)
        duration = clip_end - clip_start

        # intro/outro are standalone clips — do not clamp
        if e.get("type") in ("intro", "outro"):
            clip_start = 0.0
            duration = end - start        

     

        if e.get("type") in ("intro", "outro"):
            clip = VideoFileClip(e["clip"], audio=False)
            clip = clip.subclip(0, duration)
            segments.append(clip)
            start = end
            continue



        if e.get("type") == "free":
            if e["clip"] not in free_clip_cache:
                free_clip_cache[e["clip"]] = VideoFileClip(e["clip"], audio=False)

            base = free_clip_cache[e["clip"]]
            base_dur = base.duration

            if duration <= base_dur:
                clip = base.subclip(0, duration)
            else:
                # 🔴 IMPORTANT: re-open the clip to get a fresh reader
                SAFE = 0.05

                forward = VideoFileClip(e["clip"], audio=False).subclip(SAFE, base_dur)
                reverse = forward.fx(vfx.time_mirror)


                combined = concatenate_videoclips([forward, reverse])
                clip = combined.subclip(0, duration)


            if "mirror" in e.get("transform", []):
                clip = clip.fx(vfx.mirror_x)
            if "reverse" in e.get("transform", []):
                clip = clip.fx(vfx.time_mirror)

            segments.append(clip)
            # base.close()
            # if duration > base_dur:
            #     combined.close()



        else:
            segments.append(
                videos[e["stem"]].subclip(clip_start, clip_end)
            )



        start = end

    final = concatenate_videoclips(segments, method="compose")

    audio = AudioFileClip(final_audio_path)
    final = final.set_audio(audio).set_duration(audio.duration)

    final.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=True
    )


    for clip in free_clip_cache.values():
        clip.close()

    return output_path

# ======================================================
# GRADIO UI
# ======================================================
def render_action(
    audio_files,
    video_files,
    free_video_files,
    final_audio,
    snap_window,
    chorus_aggression,
    phrase_beats,
    downbeat_bias,
    cooldown,
    free_clip_probability,
    intro_min,
    outro_min,
    output
):

    if not final_audio:
        raise gr.Error("Final mix required")

    if not output:
        output = get_default_output_path()

    beat_times = detect_snapped_beats(final_audio.name, snap_window)
    sections = detect_sections(final_audio.name)
    song_len = AudioFileClip(final_audio.name).duration
    intro_clip = find_optional_clip("intro.mp4")
    outro_clip = find_optional_clip("outro.mp4")
    INTRO_MIN = intro_min
    OUTRO_MIN = outro_min




    free_cycler = (
        FreeClipCycler([f.name for f in free_video_files])
        if free_video_files else None
    )

    timeline, stems, video_map = generate_timeline(
        audio_files,
        video_files,
        beat_times,
        sections,
        cooldown,
        song_len,
        chorus_aggression,
        phrase_beats,
        downbeat_bias,
        free_cycler,
        free_clip_probability
    )

    if intro_clip:
        intro_end = next_beat_after(beat_times, INTRO_MIN)

        # remove anything that would play during intro
        timeline = [
            e for e in timeline
            if e["time"] >= intro_end
        ]

        # intro behaves exactly like b-roll, but fixed at start
        timeline.append({
            "time": 0.0,
            "end": intro_end,
            "type": "free",
            "clip": intro_clip,
            "transform": []
        })

    if outro_clip:
        outro_start = next_beat_after(
            beat_times,
            song_len - OUTRO_MIN
        )

        timeline.append({
            "time": outro_start,
            "end": song_len,
            "type": "free",
            "clip": outro_clip,
            "transform": []
        })

    # ✅ ensure intro/outro and beat cuts are in correct order
    timeline = sorted(timeline, key=lambda e: e["time"])
    path = build_video(timeline, stems, video_map, song_len, final_audio.name, output)
    write_edit_summary(timeline, output)


    return f"Render complete: {path}"

# with gr.Blocks() as app:
#     gr.Markdown("## 🎬 Stem-Sync Video Editor")

with gr.Blocks() as app:
    gr.Image(
        "icon.png",
        show_label=False,
        container=False
    )
    gr.Markdown("## Stem-Sync Video Editor")

    audio_files = gr.File(file_types=["audio"], file_count="multiple", label="Audio Stems")
    video_files = gr.File(file_types=["video"], file_count="multiple", label="Video Clips")
    free_video_files = gr.File(
    file_types=["video"],
    file_count="multiple",
    label="Free B-Roll Clips (non-synced)"
)
    final_audio = gr.File(file_types=["audio"], label="Final Song Audio")


    with gr.Accordion("Beat Snap Window (seconds) — click for details", open=False):
        snap_window = gr.Slider(
            0.02, 0.15, 0.08, step=0.01,
            label="Beat Snap Window (seconds)"
        )
        gr.Markdown(
            "- **What it does:** Allows detected beats to shift to the nearest strong onset (transient).\n"
            "- **Low (0.02):** Barely moves beats. More “strict grid” feel.\n"
            "- **Default (0.08):** Stronger snap to transients.\n"
            "- **High (0.15):** Most forgiving; cuts feel more like CapCut-style snapping."
        )

    with gr.Accordion("Chorus Aggression — click for details", open=False):
        chorus_aggression = gr.Slider(
            0.0, 1.0, 0.5, step=0.05,
            label="Chorus Aggression"
        )
        gr.Markdown(
            "- **What it does:** Changes how short shots can be during choruses.\n"
            "- **0.0:** Chorus behaves like verse (slower / fewer cuts).\n"
            "- **0.5:** Medium.\n"
            "- **1.0:** Fastest cutting in choruses (shortest shots)."
        )

    with gr.Accordion("Phrase Length (beats) — click for details", open=False):
        phrase_beats = gr.Slider(
            1, 8, 4, step=1,
            label="Phrase Length (beats)"
        )
        gr.Markdown(
            "- **What it does:** Minimum beats a shot should last (mainly in verse).\n"
            "- **1:** Allows very rapid cuts.\n"
            "- **4:** Typical musical phrase feel.\n"
            "- **8:** Longer, calmer shots."
        )

    with gr.Accordion("Downbeat Emphasis — click for details", open=False):
        downbeat_bias = gr.Slider(
            0, 8, 0, step=1,
            label="Downbeat Emphasis"
        )
        gr.Markdown(
            "- **What it does:** Restricts cuts to every N beats.\n"
            "- **0:** Off (can cut on any beat).\n"
            "- **2:** Cuts favor every 2 beats.\n"
            "- **4:** Bar-level feel in 4/4.\n"
            "- **8:** Even fewer cut opportunities."
        )

    with gr.Accordion("Camera Cooldown (seconds) — click for details", open=False):
        cooldown = gr.Slider(
            0.0, 10.0, 3.0, step=0.5,
            label="Camera Cooldown (seconds)"
        )
        gr.Markdown(
            "- **What it does:** Prevents reusing the same camera/clip too soon.\n"
            "- **0:** No restriction (can repeat a camera immediately).\n"
            "- **3:** Balanced variety.\n"
            "- **10:** Strong variety; repeats are rare."
        )

    with gr.Accordion("Free Clip Usage Probability — click for details", open=False):
        free_clip_probability = gr.Slider(
            0.0, 1.0, 0.2, step=0.05,
            label="Free Clip Usage Probability"
        )
        gr.Markdown(
            "- **What it does:** Chance a non-synced B-roll clip is used at a cut.\n"
            "- **0.0:** Never uses free clips.\n"
            "- **0.2:** Occasional B-roll.\n"
            "- **1.0:** Uses free clips at every possible cut (except final cut logic)."
        )

    with gr.Accordion("Intro Minimum Duration — click for details", open=False):
        intro_min = gr.Slider(
            0.0, 10.0, 3.0, step=0.5,
            label="Intro Minimum Duration (seconds) — only if intro.mp4 exists"
        )
        gr.Markdown(
            "- **What it does:** If `intro.mp4` is present, intro plays at least this long,\n"
            "  then switches on the **next beat after** that time.\n"
            "- **0:** Intro ends at the first beat/cut.\n"
            "- **10:** Intro will be at least 10s, then cut on the next beat."
        )

    with gr.Accordion("Outro Minimum Duration — click for details", open=False):
        outro_min = gr.Slider(
            0.0, 10.0, 3.0, step=0.5,
            label="Outro Minimum Duration (seconds) — only if outro.mp4 exists"
        )
        gr.Markdown(
            "- **What it does:** If `outro.mp4` is present, outro is guaranteed at least this long,\n"
            "  starting on the **next beat after** `(song_end - outro_min)`.\n"
            "- **0:** Outro starts at the last cut / near the end.\n"
            "- **10:** Outro starts earlier so it can run at least 10s to the song end."
        )


    output_path = gr.Textbox(label="Save Final As")

    render_btn = gr.Button("Render")
    status = gr.Textbox()

    render_btn.click(
        render_action,
        inputs=[
            audio_files,
            video_files,
            free_video_files,
            final_audio,
            snap_window,
            chorus_aggression,
            phrase_beats,
            downbeat_bias,
            cooldown,
            free_clip_probability,
            intro_min,
            outro_min,
            output_path
        ],
        outputs=status
    )
app.launch()
##app.launch(allowed_paths=["."])


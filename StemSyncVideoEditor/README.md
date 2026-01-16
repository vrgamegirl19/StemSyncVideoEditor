
# 🎬 Stem-Sync Video Editor

This app automatically edits music videos by cutting between full-length videos based on audio stems, beat detection, and energy levels.  
The goal is smooth, musical edits with no hard cuts and minimal manual timeline work.

This README documents both setup and my personal workflow, which is how the tool is intended to be used.

---

## Requirements

- Python 3.10+
- ffmpeg (must be installed and available in your PATH)
- Works best with audio stems (DAW exports, Suno, etc.)

---

## Install & Run

1. Unzip the project folder  
2. Run the install script  
   - Creates a virtual environment  
   - Installs all required Python packages  
3. Launch the app:

```bash
python run_app.py
```

4. Open the Gradio UI in your browser

---

## Core Concept

You provide audio stems with matching full-length videos.

The app analyzes:
- Beat positions
- Onsets / transients
- Energy per stem

It cuts only on beats, switching videos based on which stem is most active.  
Optional B-roll clips are injected probabilistically.

The result is a fully edited, beat-locked music video.

---

## Audio Stems (Required)

Each audio stem must have a corresponding video file with the same base name.

Example:

- vocals.wav → vocals.mp4  
- drums.wav → drums.mp4  
- bass.wav → bass.mp4  
- other.wav → other.mp4  

---

## Handling Many Stems (Important)

Some sources (for example Suno or DAW exports) may give you **more stems than you want to manage**.  
You do **not** need to use every stem individually.

For best results, **do not leave stems out**. Instead, **combine related stems together** so all musical energy is represented.

### Recommended Grouping Examples when doing AI video editing. 

- **Vocals** + Backup vocals → one stem ("Vocalsa")  
- **Guitars + Bass** → one stem ("Bass")  
- **Drums + Percussion** → one stem  ("Drums")
- **Synths + Keys + Pads + FX + Ambience + Misc** → one stem (“Synth”)

The editor works by comparing **relative energy between stems**, so missing stems can cause uneven or incorrect camera selection.  
Combining smaller stems ensures nothing important is ignored while keeping the stem count manageable.

I you have or want more cameras you can connect them to any stem you want. 

---

## Recommended Workflow (Practical Example)

For best results, use **full-length, continuous videos** whenever possible.  
Avoid hard cuts inside the source videos, as they can interfere with beat-locked edits and look wrong when the editor switches cameras.

### My Typical Process

1. **Generate stems**
   - Combine smaller stems so nothing is left out
   - Keep vocals separate

2. **Create two full-length base videos**
   - **Primary (Vocals):**  
     - Full song length  
     - Shows everything  
     - No intentional cuts  
     - Continuous motion and morphing  
     - I use a zimage / wan 2.2 / humo workflow that locks first + last frames so the video flows and never hard-cuts
   - **Secondary (Headshot):**  
     - Full song length  
     - Mostly head-and-shoulders framing  
     - Also continuous, no cuts

   > My workflow outputs videos in ~1 minute 4 second “sets”, small transitions between sets are fine.  
   > I normally add a transition/fade effect in CapCut or similar tools if needed to help remove the hard cut.

3. **Create variation layers**
   - Duplicate the two base videos
   - Apply:
     - Mirroring or reversing if you want
     - Color FX or visual FX
     - Other visual treatments
   - Export these as new full-length videos

4. **Create free clips (B-roll)**
   - Create ~5 short clips
   - Duplicate them
   - Mirror and reverse the duplicates
   - Apply FX as needed
   - Result: ~10 free clips total

---

## Free Clips (B‑Roll)

Optional short clips inserted at random cut points.

- Minimum ~8 seconds recommended
- Looped, mirrored, and reversed automatically
- Used to add variation without disrupting flow

---

## Intro & Outro (Optional)

Add `intro.mp4` and/or `outro.mp4` to the project root.

- Snapped to beats
- Guaranteed minimum duration
- Do not interfere with stem logic

---

## Editing Logic (High Level)

- Cuts only on beats
- Chorus sections cut faster than verses
- Camera cooldown prevents rapid reuse
- Highest-energy stem drives selection
- Timing always stays musical

---

## Output

- Final render: `.mp4`
- Edit summary: `.json`

---

## Recommended Workflow

1. Generate stems  
2. Create 2 – 4 full-length videos  
3. Add optional free clips  
4. (Optional) Add intro/outro  
5. Load assets into the app  
6. Tune sliders (try default settings first then experiment) 
7. Render

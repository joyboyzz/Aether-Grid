"""Convert actual Playwright recording to H.264 MP4; save decode metadata."""
import json, subprocess
from pathlib import Path
import imageio_ffmpeg
ROOT=Path(__file__).resolve().parents[1]/'verification'
r=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-i',str(ROOT/'AetherGrid_3min_walkthrough.webm'),
    '-c:v','libx264','-preset','fast','-crf','28','-pix_fmt','yuv420p','-movflags','+faststart','-an',
    str(ROOT/'AetherGrid_3min_walkthrough.mp4')],capture_output=True,text=True)
(ROOT/'video_encode.log').write_text(r.stderr)
if r.returncode:raise RuntimeError(r.stderr[-3000:])
reader=imageio_ffmpeg.read_frames(str(ROOT/'AetherGrid_3min_walkthrough.mp4'),pix_fmt='rgb24')
meta=next(reader);reader.close();assert 175<=meta['duration']<=190,meta
(ROOT/'video_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps(meta,indent=2))

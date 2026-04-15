
"""
app.py - Final Project: Panorama Stitcher with Edge Detection
=============================================================
This Flask web application allows users to upload multiple overlapping
photos, stitch them into a single panoramic image using OpenCV's
Stitcher (PANORAMA mode), and then apply Canny edge detection to the
resulting panorama. All three stages are displayed side-by-side in the
browser: the original uploaded images, the stitched panorama, and the
edge-detected version of the panorama.

The panorama is cached on disk between requests so the user can adjust
the edge detection threshold and re-run without re-uploading images.
A separate /reprocess route handles threshold-only updates.


To build:  docker build -t app .
To run:    docker run -p 80:80 app
Browser:   http://localhost
"""

from flask import Flask, request, render_template_string
from flask import send_from_directory
import os
import cv2
import socket
import glob

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)

# The machine hostname is shown in the UI so graders can confirm which
# container is serving the page.
hostname = socket.gethostname()

# All uploaded originals and generated images live under /static so Flask
# can serve them directly via the /static URL prefix.
UPLOAD_FOLDER = "static"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Well-known paths for the two generated images.
PANORAMA_PATH = os.path.join(UPLOAD_FOLDER, "panorama.jpg")
EDGES_PATH    = os.path.join(UPLOAD_FOLDER, "edges.jpg")

# Default Canny threshold shown in the form on first load.
LAST_T = 100

# ---------------------------------------------------------------------------
# HTML template
# ---------------------------------------------------------------------------
# Uses Jinja2. The three result panels are shown only when the relevant
# template variables are truthy (originals, panorama, processed).
# A second lightweight form lets the user adjust only the threshold when
# a panorama is already cached on disk.
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Panorama Stitcher</title>
<link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
  /* ── Design tokens ─────────────────────────────────────────── */
  :root {
    --bg:       #f5f0e8;   /* warm parchment                    */
    --surface:  #fffdf7;   /* slightly warmer white for cards   */
    --border:   #ddd5c0;   /* tan border                        */
    --accent:   #e8622a;   /* sunset orange                     */
    --accent2:  #d4a853;   /* warm amber / golden hour          */
    --text:     #2c2416;   /* deep warm brown                   */
    --muted:    #9a8870;   /* muted tan                         */
    --radius:   6px;
  }

  /* ── Reset & base ──────────────────────────────────────────── */
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Space Mono', monospace;
    font-size: 14px;
    min-height: 100vh;
    padding: 40px 32px 80px;
  }

  /* ── Header ────────────────────────────────────────────────── */
  header {
    border-bottom: 1px solid var(--border);
    padding-bottom: 14px;
    margin-bottom: 24px;
  }
  header h1 {
    font-family: 'Syne', sans-serif;
    font-size: clamp(1.8rem, 5vw, 3rem);
    font-weight: 800;
    letter-spacing: -0.02em;
    line-height: 1;
  }
  header h1 span { color: var(--accent); }
  header p { color: var(--muted); margin-top: 6px; font-size: 12px; }

  /* ── Section label ─────────────────────────────────────────── */
  .section-label {
    font-size: 11px;
    font-weight: 700;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .12em;
    margin-bottom: 10px;
  }

  /* ── Cards shared style ────────────────────────────────────── */
  .form-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 24px;
    display: flex;
    flex-wrap: wrap;
    gap: 20px;
    align-items: flex-end;
    max-width: 860px;
    margin-bottom: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }

  /* Two control cards should share equal half-width columns and height */
  .controls-row {
    display: flex;
    gap: 20px;
    align-items: stretch;
    width: 100%;
    margin-bottom: 4px;
  }
  .control-col {
    flex: 1 1 0;
    min-width: 0;
  }
  .control-col .form-card {
    width: 100%;
    max-width: none;
    min-height: 160px;
    margin-bottom: 0;
  }

  @media (max-width: 860px) {
    .controls-row { flex-direction: column; }
  }

  /* Threshold-only card is visually lighter / amber-tinted */
  .form-card.reprocess {
    background: #fdf5e8;
    border-color: var(--accent2);
    margin-bottom: 8px;
  }

  .field { display: flex; flex-direction: column; gap: 6px; }
  label  { font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; }

  /* File input */
  input[type="file"] {
    background: #f0ebe0;
    border: 1px dashed var(--border);
    border-radius: var(--radius);
    color: var(--text);
    padding: 10px 14px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13px;
    width: 340px;
  }
  input[type="file"]:hover { border-color: var(--accent); }

  /* Number input */
  input[type="number"] {
    background: #f0ebe0;
    border: 1px solid var(--border);
    border-radius: var(--radius);
    color: var(--text);
    font-family: inherit;
    font-size: 14px;
    padding: 10px 14px;
    width: 120px;
  }
  input[type="number"]:focus { outline: none; border-color: var(--accent); }

  /* Primary button */
  button[type="submit"] {
    background: var(--accent);
    border: none;
    border-radius: var(--radius);
    color: #fff;
    cursor: pointer;
    font-family: 'Syne', sans-serif;
    font-size: 14px;
    font-weight: 700;
    padding: 11px 28px;
    letter-spacing: .04em;
    transition: opacity .15s, transform .1s;
  }
  button[type="submit"]:hover  { opacity: .88; }
  button[type="submit"]:active { transform: scale(.97); }

  /* Secondary / outline button used for re-process */
  button.secondary {
    background: transparent;
    border: 2px solid var(--accent2);
    color: var(--accent);
  }
  button.secondary:hover { background: #fdebd0; }

  /* Small hint text beneath the reprocess form */
  .hint {
    font-size: 11px;
    color: var(--muted);
    max-width: 860px;
    margin-bottom: 40px;
    padding-left: 2px;
  }

  /* ── Results section ───────────────────────────────────────── */
  .results-header {
    font-family: 'Syne', sans-serif;
    font-size: 1.1rem;
    font-weight: 700;
    margin-bottom: 20px;
    border-left: 3px solid var(--accent);
    padding-left: 12px;
    color: var(--text);
  }

  /* Three-panel layout */
  .panels {
    display: grid;
    grid-template-columns: 1fr 2fr 2fr;
    gap: 20px;
    align-items: start;
  }
  @media (max-width: 860px) {
    .panels { grid-template-columns: 1fr; }
  }

  .panel {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,.06);
  }
  .panel-title {
    padding: 10px 14px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: .1em;
    border-bottom: 1px solid var(--border);
    display: flex;
    align-items: center;
    gap: 8px;
    background: #faf6ee;
  }
  .panel-title .dot {
    width: 8px; height: 8px;
    border-radius: 50%;
    background: var(--muted);
    flex-shrink: 0;
  }
  .panel-title .dot.orange { background: var(--accent); }
  .panel-title .dot.gold   { background: var(--accent2); }

  .panel-body { padding: 14px; }

  /* Original images stacked vertically */
  .originals-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .originals-list img {
    width: 100%;
    border-radius: 4px;
    display: block;
    border: 1px solid var(--border);
  }

  /* Panorama / edge images fill the panel */
  .panel-body img.full {
    width: 100%;
    border-radius: 4px;
    display: block;
    border: 1px solid var(--border);
  }

  /* ── Error / info banner ───────────────────────────────────── */
  .banner {
    background: #fdf0ec;
    border: 1px solid #e8b49a;
    border-radius: var(--radius);
    color: #b03a1a;
    padding: 14px 18px;
    max-width: 860px;
    margin-bottom: 28px;
    font-size: 13px;
  }

  
</style>
</head>

<body>

<header>
    <div style="display:flex; justify-content:space-between; align-items:flex-start; width:100%;">

        <div>
        <h1>Panorama <span>Stitcher</span></h1>
        <p>host={{ hostname }} &nbsp;|&nbsp; Upload overlapping photos → stitch → edge detect</p>
        </div>

        <div>
            <p class="section-label">Sample Images</p>
                <div class="form-card" style="gap:12px;">

                <a href="/sample-images/image1.png" download>
                    <button type="button" class="secondary">Download Image 1</button>
                </a>

                <a href="/sample-images/image2.png" download>
                    <button type="button" class="secondary">Download Image 2</button>
                </a>

                <a href="/sample-images/image3.png" download>
                    <button type="button" class="secondary">Download Image 3</button>
                </a>

                </div>
        </div>
    </div>
</header>



<div class="controls-row">
    <div class="control-col">
        <!-- ── Form 1: full upload + stitch ───────────────────────────── -->
        <p class="section-label">Upload &amp; Stitch</p>
        <form method="POST" action="/stitch" enctype="multipart/form-data">
        <div class="form-card">

            <div class="field">
            <label>Images — select 2 or more overlapping photos</label>
            <input type="file" name="files" multiple accept="image/*">
            </div>

            <div class="field">
            <label>Edge Threshold (T)</label>
            <input type="number" name="T" value="{{ threshold }}" min="1" max="500">
            </div>

            <button type="submit">Stitch &amp; Detect</button>

        </div>
        </form>
    </div>

    <div class="control-col">
        <!-- ── Form 2: threshold-only re-run, shown when panorama exists  -->
        {% if panorama_cached %}
        <p class="section-label">Adjust Edge Threshold</p>
        <form method="POST" action="/reprocess">
        <div class="form-card reprocess">

            <div class="field">
            <label>New Edge Threshold (T)</label>
            <input type="number" name="T" value="{{ threshold }}" min="1" max="500">
            </div>

            <button type="submit" class="secondary">Re-Detect Edges</button>

        </div>
        </form>
        <p class="hint">↑ Re-runs edge detection on the cached panorama — no need to re-upload.</p>
        {% endif %}
        </div>
    </div>


<!-- ── Error banner ────────────────────────────────────────────── -->
{% if error %}
<div class="banner">⚠ {{ error }}</div>
{% endif %}

<!-- ── Three-panel results ─────────────────────────────────────── -->
{% if originals and panorama and processed %}

<div class="results-header">Results — Edge Threshold: {{ threshold }}</div>

<div class="panels">

  <!-- Panel 1: original uploaded images stacked -->
  <div class="panel">
    <div class="panel-title">
      <span class="dot"></span>
      Originals ({{ originals|length }})
    </div>
    <div class="panel-body">
      <div class="originals-list">
        {% for img in originals %}
        <img src="{{ img }}" alt="original {{ loop.index }}">
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- Panel 2: stitched panorama -->
  <div class="panel">
    <div class="panel-title">
      <span class="dot orange"></span>
      Panorama
    </div>
    <div class="panel-body">
      <img class="full" src="{{ panorama }}" alt="panorama">
    </div>
  </div>

  <!-- Panel 3: edge-detected panorama -->
  <div class="panel">
    <div class="panel-title">
      <span class="dot gold"></span>
      Edge Detection (Canny)
    </div>
    <div class="panel-body">
      <img class="full" src="{{ processed }}" alt="edge detected">
    </div>
  </div>

</div>

{% endif %}

<script>
  // Save scroll position before reload
  window.addEventListener("beforeunload", function () {
    localStorage.setItem("scrollY", window.scrollY);
  });

  // Restore scroll position after reload
  window.addEventListener("load", function () {
    const scrollY = localStorage.getItem("scrollY");
    if (scrollY !== null) {
      window.scrollTo(0, parseInt(scrollY));
    }
  });
</script>

</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def panorama_is_cached():
    """
    Return True if a stitched panorama from a previous request still
    exists on disk. Used to decide whether to show the threshold-only form.
    """
    return os.path.exists(PANORAMA_PATH)


def original_urls_from_disk():
    """
    Rebuild the list of /static/original_N.jpg URLs by scanning the
    static folder. Used after a /reprocess request so the originals
    panel can still be populated without re-uploading.

    Returns a list sorted by numeric suffix so images appear in the
    correct left-to-right order.
    """
    paths = sorted(
        glob.glob(os.path.join(UPLOAD_FOLDER, "original_*.jpg")),
        key=lambda p: int(os.path.splitext(os.path.basename(p))[0].split("_")[1])
    )
    return ["/static/" + os.path.basename(p) for p in paths]


def stitch_images(image_paths):
    """
    Stitch a list of image file paths into a single panoramic image.

    Parameters
    ----------
    image_paths : list[str]
        Paths to the uploaded image files, already sorted in the correct
        left-to-right order by the caller.

    Returns
    -------
    tuple (status: str, panorama: numpy.ndarray or None)
        status   – 'ok' on success, or a human-readable error string.
        panorama – The stitched image array, or None on failure.

    Implementation notes
    --------------------
    We use cv2.Stitcher.create(cv2.Stitcher_PANORAMA) rather than
    Stitcher_SCANS because PANORAMA mode handles the projective
    distortion that occurs when photos are taken by hand (the camera
    rotates around a point so straight lines appear curved). SCANS is
    intended for flat documents photographed from directly above.
    """
    # Read each image file into a numpy array for OpenCV to process.
    imgs = []
    for path in image_paths:
        img = cv2.imread(path)
        if img is None:
            return f"Could not read image: {os.path.basename(path)}", None
        imgs.append(img)

    if len(imgs) < 2:
        return "Please upload at least 2 images to stitch.", None

    # Create the stitcher in PANORAMA mode (handles hand-held camera rotation).
    stitcher = cv2.Stitcher.create(cv2.Stitcher_PANORAMA)

    # stitch() returns a numeric status code and the result image.
    # Status codes:
    #   cv2.Stitcher_OK (0)                        – success
    #   cv2.Stitcher_ERR_NEED_MORE_IMGS            – not enough feature matches
    #   cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL       – motion estimation failed
    #   cv2.Stitcher_ERR_CAMERA_PARAMS_ADJUST_FAIL – parameter adjustment failed
    status, pano = stitcher.stitch(imgs)

    if status == cv2.Stitcher_OK:
        return "ok", pano
    elif status == cv2.Stitcher_ERR_NEED_MORE_IMGS:
        return ("Stitching failed: not enough matching features between images. "
                "Make sure photos overlap by at least 30–50%."), None
    elif status == cv2.Stitcher_ERR_HOMOGRAPHY_EST_FAIL:
        return ("Stitching failed: could not estimate camera motion. "
                "Try photos with more overlap or distinctive features."), None
    else:
        return f"Stitching failed with OpenCV status code {status}.", None


def detect_edges(input_path, output_path, T=100):
    """
    Apply Canny edge detection to the image at input_path and write the
    result to output_path.

    Parameters
    ----------
    input_path  : str – path to the source image (the panorama).
    output_path : str – path where the edge image will be saved.
    T           : int – upper Canny threshold; lower threshold = T * 0.5.

    Returns
    -------
    str – output_path confirming where the file was saved.

    Canny thresholds explained:
      T1 (low)  – edges whose gradient magnitude falls below T1 are
                  discarded outright.
      T2 (high) – edges above T2 are always kept as strong edges.
      Edges between T1 and T2 are kept only when they connect to a T2
      edge (hysteresis). Using T1 = T/2 is a widely used heuristic.
    """
    # Derive the two Canny thresholds from the single user-supplied value.
    T1 = int(T * 0.5)   # lower hysteresis threshold
    T2 = int(T)          # upper hysteresis threshold

    # Load the panorama and apply Canny edge detection.
    img   = cv2.imread(input_path)
    edges = cv2.Canny(img, T1, T2)

    # Write the single-channel (grayscale) edge image to disk.
    cv2.imwrite(output_path, edges)
    return output_path


def clear_originals():
    """
    Delete any previously saved original_N.jpg files from the static
    folder. Called before saving a fresh set of uploads so stale images
    from a prior request are not mixed with new ones.

    The panorama and edges files are intentionally NOT cleared here so
    that the /reprocess route can still access the cached panorama.
    """
    for f in glob.glob(os.path.join(UPLOAD_FOLDER, "original_*.jpg")):
        os.remove(f)


def clear_all_files():
    """
    Delete all generated files (originals, panorama, edges). Called at
    the start of a full /stitch request so nothing carries over from a
    previous session.
    """
    clear_originals()
    for name in ("panorama.jpg", "edges.jpg"):
        path = os.path.join(UPLOAD_FOLDER, name)
        if os.path.exists(path):
            os.remove(path)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/sample-images/<filename>")
def sample_images(filename):
    return send_from_directory("static/images", filename, as_attachment=True)

@app.route("/")
def home():
    """
    Render the home page with an empty upload form.
    If a panorama is already cached on disk from a previous session, the
    threshold-only form is also shown so the user can re-detect edges
    immediately without re-uploading. No result panels are shown here.
    """
    return render_template_string(
        HTML,
        threshold=LAST_T,
        hostname=hostname,
        originals=None,
        panorama=None,
        processed=None,
        panorama_cached=panorama_is_cached(),
        error=None,
    )


@app.route("/stitch", methods=["POST"])
def stitch_route():
    """
    Handle a full upload-and-stitch POST from the main form.

    Steps
    -----
    1. Read the Canny threshold (T) from the form.
    2. Collect all uploaded files via request.files.getlist().
       getlist() returns every file from a multi-file input, unlike
       get() which only returns the first one.
    3. Sort uploaded files by filename so images are stitched in the
       correct left-to-right order regardless of browser upload order.
    4. Clear all previously generated files.
    5. Save each uploaded file to static/original_N.jpg.
    6. Call stitch_images() to produce a panorama with OpenCV.
    7. Save the panorama to static/panorama.jpg.
    8. Call detect_edges() to produce static/edges.jpg.
    9. Render the template with all three panels populated.
    """
    # ── 1. Read threshold ─────────────────────────────────────────
    T = request.form.get("T", default=100, type=int)

    # ── 2. Collect uploaded files ─────────────────────────────────
    # getlist("files") returns a list of FileStorage objects for all
    # files selected in the <input type="file" multiple> field.
    uploaded_files = request.files.getlist("files")

    # Drop any empty slots the browser may have included.
    uploaded_files = [f for f in uploaded_files if f and f.filename != ""]

    if not uploaded_files:
        return render_template_string(
            HTML,
            threshold=T, hostname=hostname,
            originals=None, panorama=None, processed=None,
            panorama_cached=panorama_is_cached(),
            error="No files were uploaded. Please select at least 2 images.",
        )

    if len(uploaded_files) < 2:
        return render_template_string(
            HTML,
            threshold=T, hostname=hostname,
            originals=None, panorama=None, processed=None,
            panorama_cached=panorama_is_cached(),
            error="Please upload at least 2 overlapping images for stitching.",
        )

    # ── 3. Sort by filename for correct left-to-right order ───────
    # Browsers do not guarantee that files arrive in the order the user
    # selected them. Sorting by filename ensures files named 1.jpg,
    # 2.jpg, 3.jpg are always stitched in that sequence.
    uploaded_files = sorted(uploaded_files, key=lambda f: f.filename)

    # ── 4. Clear all old files ────────────────────────────────────
    clear_all_files()

    # ── 5. Save each uploaded file with a numbered name ───────────
    saved_paths   = []   # filesystem paths used by OpenCV
    original_urls = []   # /static/… URLs passed to the template

    for i, f in enumerate(uploaded_files):
        filename  = f"original_{i}.jpg"
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        f.save(save_path)
        saved_paths.append(save_path)
        original_urls.append(f"/static/{filename}")

    # ── 6. Stitch into a panorama ─────────────────────────────────
    stitch_status, pano_img = stitch_images(saved_paths)

    if stitch_status != "ok":
        # Stitching failed – show originals and a helpful error message.
        return render_template_string(
            HTML,
            threshold=T, hostname=hostname,
            originals=original_urls, panorama=None, processed=None,
            panorama_cached=False,
            error=stitch_status,
        )

    # ── 7. Save the panorama to the well-known PANORAMA_PATH ──────
    # Using a fixed path means the /reprocess route can find it later
    # without needing the user to re-upload anything.
    cv2.imwrite(PANORAMA_PATH, pano_img)

    # ── 8. Run edge detection on the panorama ─────────────────────
    detect_edges(PANORAMA_PATH, EDGES_PATH, T)

    # ── 9. Render results ─────────────────────────────────────────
    return render_template_string(
        HTML,
        threshold=T, hostname=hostname,
        originals=original_urls,
        panorama="/static/panorama.jpg",
        processed="/static/edges.jpg",
        panorama_cached=True,
        error=None,
    )


@app.route("/reprocess", methods=["POST"])
def reprocess_route():
    """
    Re-run edge detection on the already-cached panorama with a new
    threshold value. No file upload is required.

    This allows the user to experiment with the Canny threshold without
    waiting for the (often slow) stitching step to repeat.

    Steps
    -----
    1. Read the new threshold (T) from the form.
    2. Verify that a cached panorama exists on disk.
    3. Call detect_edges() with the new threshold.
    4. Rebuild the list of original image URLs from disk.
    5. Render the same three-panel template as the full stitch route.
    """
    # ── 1. Read new threshold ─────────────────────────────────────
    T = request.form.get("T", default=100, type=int)

    # ── 2. Check that the cached panorama is available ────────────
    if not panorama_is_cached():
        return render_template_string(
            HTML,
            threshold=T, hostname=hostname,
            originals=None, panorama=None, processed=None,
            panorama_cached=False,
            error="No cached panorama found. Please upload images and stitch first.",
        )

    # ── 3. Re-run edge detection with the new threshold ───────────
    # PANORAMA_PATH and EDGES_PATH are module-level constants so both
    # this route and stitch_route always read/write the same files.
    detect_edges(PANORAMA_PATH, EDGES_PATH, T)

    # ── 4. Rebuild original image URLs from whatever is on disk ───
    # The original files were saved during the last /stitch request
    # and are still present, so we can reconstruct their URLs without
    # needing the user to re-upload anything.
    original_urls = original_urls_from_disk()

    # ── 5. Render results ─────────────────────────────────────────
    return render_template_string(
        HTML,
        threshold=T, hostname=hostname,
        originals=original_urls,
        panorama="/static/panorama.jpg",
        processed="/static/edges.jpg",
        panorama_cached=True,
        error=None,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Read PORT from environment so Docker can override via -e PORT=…
    # Default is 80 to match the Dockerfile EXPOSE and the run instructions.
    port = int(os.environ.get("PORT", 80))
    app.run(host="0.0.0.0", port=port)

Custom Gauge Image Generator and ICL Optimizer
A Streamlit-based toolkit that lets you create richly styled gauge charts (round or linear, continuous or segmented) with live D3.js preview and one-click PNG export, plus an ICL memory-block file allocator. Perfect for embedded-GUI prototyping and flash-image planning.

Features
Live D3.js Preview
Adjust gauge value, colors, thickness, angles, 3D effect, segmentation, name & value labels in real time.

Instant Export
Download your current gauge or batch-generate 0–99 PNGs in a ZIP.

Linear & Round Gauges
Choose between smooth arcs or segmented bars, horizontal or vertical layouts.

ICL Optimizer
Upload .icl files, specify start/end blocks, detect overlaps/out-of-range and propose a compact re-allocation with new filenames & ZIP download.

Dark-theme UI
Clean, high-contrast interface with full sidebar controls.

Installation
bash
Copy
Edit
git clone https://github.com/gcharles81/DWIN-Guage-creator.git
cd DWIN-Guage-creator
pip install -r requirements.txt
streamlit run app.py
Usage
Live Preview Tab
Use the sidebar to configure your gauge; watch the D3.js preview update live.

Download Gauges
Click “Download Current Gauge” or “Generate and Download All Gauges (0–99)”.

ICL Optimizer Tab
Upload your .icl files, set block range, review original vs. optimized allocation, then download the renamed ZIP.

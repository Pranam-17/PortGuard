# Smart PortGuard — Rebuilt from scratch

Same dark Air/Water dashboard style with real-time ESP32 readings, persistent SQLite + CSV logging, ML water-trend/anomaly analysis, alerts, and CSV/Excel reports.

Run:
`python -m pip install -r requirements.txt`
`python app.py`
Open `http://localhost:5001/`.

Air ESP32: `http://<LAPTOP-IP>:5001/api/air`
Water ESP32: `http://<LAPTOP-IP>:5001/api/water`
Legacy: `http://<LAPTOP-IP>:5001/sensor-data`

The ML trend engine analyzes the monitored project's collected water history; it does not claim to measure the entire ocean. MQ135 ADC is kept as raw ADC and is not mislabeled as ppm.

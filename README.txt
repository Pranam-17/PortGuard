SMART PORTGUARD — AIR + WATER NODE WEBSITE

Run:
1. Open Command Prompt in this folder.
2. pip install -r requirements.txt
3. python app.py
4. Open http://localhost:5001

ESP32 Air Node:
POST JSON to http://YOUR_LAPTOP_IP:5001/api/air
{
  "node":"air",
  "temperature":29.4,
  "humidity":78.5,
  "pressure":1011.8,
  "mq135_1":2261,
  "mq135_2":2407,
  "air_quality":113
}

ESP32 Water Node:
POST JSON to http://YOUR_LAPTOP_IP:5001/api/water
{
  "node":"water",
  "ph":7.2,
  "tds":420,
  "turbidity":11.5,
  "water_temperature":29.4
}

Both nodes can use the same laptop and Wi-Fi. The dashboard has separate Air Node and Water Node tabs.


Backward compatibility:
The Air Node can also POST its Air payload to /sensor-data.
Example: http://YOUR_LAPTOP_IP:5001/sensor-data

The dashboard itself reads /api/air and /api/water every 2 seconds.

from prometheus_client import Counter, Gauge, start_http_server

# Counters
serial_packets_read = Counter("serial_packets_read_total", "Number of serial packets read")
serial_write_errors = Counter("serial_write_errors_total", "Number of serial write errors")
mqtt_messages_published = Counter("mqtt_messages_published_total", "Number of MQTT messages published")
mqtt_messages_failed = Counter("mqtt_messages_failed_total", "Number of MQTT messages failed")
camera_frames_sent = Counter("camera_frames_sent_total", "Number of camera frames sent")

# Gauges
connected_serial_devices = Gauge("connected_serial_devices", "Currently connected serial devices")

def start_metrics_server(port: int = 8000):
    start_http_server(port)


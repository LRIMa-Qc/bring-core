## Sending data

Recieved data (from UART) is divided into two parts:

- The first byte which represents the data type
- The following bytes which represent the actual data (ask Leo why)

The following data is reversed and then sent to the following MQTT topic: `device/{data_type}`.

## Receiving data

Received data from MQTT (at `device/write`) is sent via UART to the PCB.

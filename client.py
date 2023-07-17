import bluetooth
# Returns True if the Bluetooth is connected. Always true when using the REPL, but useful for saved scripts
bluetooth.connected()
len = bluetooth.max_length()  # Returns the maximum payload size we can send in one go

str = "world hello"
# Sends the string 'hello world' to the host. Limited by the maximum payload size
bluetooth.send(str[:len])

# Define a callback function which is triggered upon reception of Bluetooth data from the host


def fn(bytes):
    print(bytes)


# Attaches the above function to the receive callback
bluetooth.receive_callback(fn)

import pyaudiowpatch as pa

try:
    p = pa.PyAudio()
    print("--- All Devices ---")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        print(f"Index {i}: {info['name']} (In: {info['maxInputChannels']}, Out: {info['maxOutputChannels']})")

    print("\n--- Loopback Devices ---")
    for device in p.get_loopback_device_info_generator():
        print(f"Name: {device['name']}, Index: {device['index']}")
        
    print("\n--- WASAPI Host API Info ---")
    try:
        wasapi_info = p.get_host_api_info_by_type(pa.paWASAPI)
        print(f"Default Input: {wasapi_info.get('defaultInputDevice')}")
        print(f"Default Output: {wasapi_info.get('defaultOutputDevice')}")
    except Exception as e:
        print(f"WASAPI info error: {e}")

    p.terminate()
except Exception as e:
    print(f"Error: {e}")

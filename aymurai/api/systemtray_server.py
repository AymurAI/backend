import os
import threading
import time

import pystray
import uvicorn
from PIL import Image

from aymurai.settings import settings

# Global flag to signal shutdown
shutdown_flag = threading.Event()


# Callback for the tray menu's Quit action
def quit_action(icon, item):
    icon.stop()  # Stop the tray icon loop
    shutdown_flag.set()  # Signal the API server to shut down


# Function to run the system tray icon
def start_tray():
    icon = Image.open(os.path.join(settings.ASSETS_BASEPATH, "favicon.ico"))
    menu = pystray.Menu(pystray.MenuItem("Quit", quit_action))
    icon = pystray.Icon("AymurAI", icon, "AymurAI", menu)
    icon.run()


def main():
    # Start the system tray in a separate thread
    tray_thread = threading.Thread(target=start_tray, daemon=True)
    tray_thread.start()

    # Start the API server in the main thread (or another thread)
    config = uvicorn.Config(
        "aymurai.api.main:api", host="127.0.0.1", port=8000, log_level="info"
    )
    server = uvicorn.Server(config)

    # Run the server in a thread so we can monitor shutdown_flag
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()

    # Wait for shutdown signal
    while not shutdown_flag.is_set():
        time.sleep(0.5)

    # Trigger server shutdown
    server.should_exit = True
    server_thread.join()


if __name__ == "__main__":
    main()

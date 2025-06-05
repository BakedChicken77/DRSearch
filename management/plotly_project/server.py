from threading import Event
import uvicorn
import threading

class Server:
    def __init__(self):
        self.stop_event = Event()

    def run(self, app, port):
        config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info", reload=True)
        server = uvicorn.Server(config)

        thread = threading.Thread(target=server.run)
        thread.start()

        self.thread = thread
        self.server = server

    def stop(self):
        self.server.should_exit = True
        self.thread.join()

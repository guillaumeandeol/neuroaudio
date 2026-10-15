"""Lecture audio. SdPlayer utilise sounddevice (PortAudio) ; DummyPlayer simule la durée (tests, --no-audio)."""
import threading


class DummyPlayer:
    name = "simulation (aucun son)"

    def __init__(self):
        self._token = 0
        self._timer = None

    def play(self, data, fs, on_done):
        self.stop()
        tok = self._token
        self._timer = threading.Timer(len(data) / fs * 0.02, lambda: tok == self._token and on_done())  # 50x plus vite
        self._timer.start()

    def stop(self):
        self._token += 1
        if self._timer:
            self._timer.cancel()


class SdPlayer:
    def __init__(self, device=None):
        import sounddevice as sd
        self.sd = sd
        self.device = device
        self._token = 0
        self.name = "sounddevice"

    @staticmethod
    def devices():
        import sounddevice as sd
        out = []
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] >= 2:
                out.append((i, d["name"]))
        return out

    def play(self, data, fs, on_done):
        self.stop()
        tok = self._token
        self.sd.play(data, fs, device=self.device)

        def waiter():
            try:
                self.sd.wait()
            finally:
                if tok == self._token:
                    on_done()
        threading.Thread(target=waiter, daemon=True).start()

    def stop(self):
        self._token += 1
        try:
            self.sd.stop()
        except Exception:
            pass


def make_player(no_audio=False, device=None):
    if no_audio:
        return DummyPlayer()
    return SdPlayer(device)

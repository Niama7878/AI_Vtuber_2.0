import queue
import threading
import pyaudio
import wave
import io

class AudioPlayer:
    def __init__(self):
        self.audio_queue = queue.Queue()
        self._is_playing = False  
        self.running = True  
        self.p = pyaudio.PyAudio()
        
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=24000,
            output=True,
        ) 
        self.thread = threading.Thread(target=self._play_loop, daemon=True)
        self.thread.start()

    def add_audio(self, audio: bytes):
        """添加音频到播放队列"""
        self.audio_queue.put(audio)
    
    @property
    def is_playing(self):
        return self._is_playing
    
    @is_playing.setter
    def is_playing(self, value):
        self._is_playing = value

    def _play_loop(self):
        """循环播放队列中的音频"""
        while self.running:
            try:
                audio = self.audio_queue.get(timeout=0.01) 
                self.is_playing = True 
                self._play_audio(audio)
                self.is_playing = False 
            except queue.Empty:
                continue  

    def _play_audio(self, audio: bytes):
        """持续播放音频，不关闭 stream"""
        wf = wave.open(io.BytesIO(audio), 'rb')
        
        chunk_size = 1024
        data = wf.readframes(chunk_size)
        while data:
            self.stream.write(data)
            data = wf.readframes(chunk_size)
# WebSocket Media Streams Handler for Real-time Interruption
import asyncio
import json
import base64
import logging
import audioop
from collections import deque
import struct

logger = logging.getLogger(__name__)

class TwilioMediaStreamHandler:
    """Handle Twilio Media Streams for real-time audio processing and interruption"""
    
    def __init__(self):
        self.stream_sid = None
        self.call_sid = None
        self.is_ai_speaking = False
        self.audio_buffer = deque(maxlen=100)  # Keep last 2 seconds of audio
        
        # Audio settings for Twilio (mulaw 8kHz)
        self.sample_rate = 8000
        self.frame_duration = 20  # ms per frame
        self.frame_size = int(self.sample_rate * self.frame_duration / 1000)  # 160 samples
        
        # Interruption detection using RMS (Root Mean Square) audio level
        self.speech_frames = 0
        self.silence_frames = 0
        self.speech_threshold = 10  # Consecutive frames to detect speech
        self.rms_threshold = 500  # RMS amplitude threshold for speech
        
    async def handle_message(self, websocket, message):
        """Handle incoming WebSocket messages from Twilio"""
        try:
            data = json.loads(message)
            event_type = data.get('event')
            
            if event_type == 'start':
                await self.handle_start(data)
            elif event_type == 'media':
                await self.handle_media(websocket, data)
            elif event_type == 'stop':
                await self.handle_stop(data)
            elif event_type == 'mark':
                await self.handle_mark(data)
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            
    async def handle_start(self, data):
        """Handle stream start event"""
        self.stream_sid = data['start']['streamSid']
        self.call_sid = data['start']['callSid']
        custom_params = data['start'].get('customParameters', {})
        
        logger.info(f"🎙️ Media stream started: {self.stream_sid}")
        logger.info(f"📞 Call SID: {self.call_sid}")
        
    async def handle_media(self, websocket, data):
        """Handle incoming audio data"""
        try:
            # Get audio payload (base64 encoded mulaw)
            payload = data['media']['payload']
            timestamp = data['media']['timestamp']
            
            # Decode audio
            audio_data = base64.b64decode(payload)
            
            # Convert mulaw to linear PCM for VAD
            pcm_audio = audioop.ulaw2lin(audio_data, 2)  # 2 bytes per sample
            
            # Add to buffer
            self.audio_buffer.append(pcm_audio)
            
            # If AI is speaking, check for customer interruption
            if self.is_ai_speaking:
                if await self.detect_speech(pcm_audio):
                    await self.handle_interruption(websocket)
                    
        except Exception as e:
            logger.error(f"Error handling media: {e}")
            
    async def detect_speech(self, pcm_audio):
        """Detect if customer is speaking using RMS (Root Mean Square) audio level"""
        try:
            # Calculate RMS (Root Mean Square) of the audio
            # RMS is a measure of audio amplitude/loudness
            rms = audioop.rms(pcm_audio, 2)  # 2 bytes per sample (16-bit PCM)
            
            # Check if RMS exceeds threshold (indicating speech)
            is_speech = rms > self.rms_threshold
            
            if is_speech:
                self.speech_frames += 1
                self.silence_frames = 0
            else:
                self.silence_frames += 1
                if self.silence_frames > 5:
                    self.speech_frames = 0
            
            # Return True if we have consistent speech
            if self.speech_frames >= self.speech_threshold:
                logger.info(f"🎤 Speech detected! RMS: {rms} (threshold: {self.rms_threshold})")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Speech detection error: {e}")
            return False
            
    async def handle_interruption(self, websocket):
        """Handle customer interrupting AI"""
        if not self.is_ai_speaking:
            return
            
        logger.info("🎤 CUSTOMER INTERRUPTED - Stopping AI speech!")
        
        # Stop AI from speaking
        self.is_ai_speaking = False
        
        # Send clear command to Twilio to stop current audio
        clear_message = {
            'event': 'clear',
            'streamSid': self.stream_sid
        }
        
        await websocket.send(json.dumps(clear_message))
        logger.info("✅ Sent clear command to stop AI audio")
        
        # Reset speech detection
        self.speech_frames = 0
        self.silence_frames = 0
        
    async def handle_stop(self, data):
        """Handle stream stop event"""
        logger.info(f"🛑 Media stream stopped: {self.stream_sid}")
        
    async def handle_mark(self, data):
        """Handle mark events (for synchronization)"""
        mark_name = data.get('mark', {}).get('name')
        logger.debug(f"Mark received: {mark_name}")
        
    def set_ai_speaking(self, speaking: bool):
        """Set whether AI is currently speaking"""
        self.is_ai_speaking = speaking
        if speaking:
            logger.info("🤖 AI started speaking - interruption detection enabled")
            # Reset detection counters
            self.speech_frames = 0
            self.silence_frames = 0
        else:
            logger.info("🤖 AI finished speaking - interruption detection disabled")


# Store active stream handlers by call SID
active_streams = {}

def get_stream_handler(call_sid):
    """Get or create stream handler for a call"""
    if call_sid not in active_streams:
        active_streams[call_sid] = TwilioMediaStreamHandler()
    return active_streams[call_sid]

def cleanup_stream(call_sid):
    """Clean up stream handler when call ends"""
    if call_sid in active_streams:
        del active_streams[call_sid]
        logger.info(f"🧹 Cleaned up stream handler for call {call_sid}")


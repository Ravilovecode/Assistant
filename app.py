# app.py
from flask import Flask, render_template, request
from flask_socketio import SocketIO
import google.generativeai as genai
import os
import speech_recognition as sr
from gtts import gTTS
import base64
import io
import logging
import requests
import tempfile
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_receptionist.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load and configure APIs
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=GEMINI_API_KEY)

# Initialize Twilio client
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    logger.warning("Twilio credentials not found - phone functionality will be limited")

# Configure Gemini model (use gemini-1.5-flash for speed)
model = genai.GenerativeModel('gemini-2.5-flash')

# Home route
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/voice', methods=['POST'])
def voice():
    """Handle incoming Twilio voice calls"""
    logger.info("Incoming voice call received")
    response = VoiceResponse()
    
    # Professional greeting
    greeting = """Hello! You've reached our AI receptionist. 
    I'm here to help you with any questions you may have. 
    Please speak your question after the beep, and I'll do my best to assist you."""
    
    response.say(greeting, voice='alice', language='en')
    response.record(
        action="/process_voice", 
        method="POST", 
        max_length=30,  # 30 seconds max
        play_beep=True,
        transcribe=True,
        timeout=5  # 5 seconds of silence before ending
    )
    
    return str(response)

@app.route('/process_voice', methods=['POST'])
def process_voice():
    """Process the recorded voice message and generate AI response"""
    logger.info("Processing voice recording...")
    
    try:
        recording_url = request.form.get('RecordingUrl')
        transcription = request.form.get('TranscriptionText', '')
        
        if not recording_url:
            logger.error("No recording URL provided")
            response = VoiceResponse()
            response.say("I'm sorry, I didn't receive your recording. Please try calling again.", voice='alice')
            return str(response)
        
        # Download the audio file from Twilio
        audio_response = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        
        if audio_response.status_code != 200:
            logger.error(f"Failed to download recording: {audio_response.status_code}")
            response = VoiceResponse()
            response.say("I'm sorry, there was a technical issue. Please try calling again.", voice='alice')
            return str(response)
        
        # Use transcription if available, otherwise transcribe the audio
        if transcription:
            query = transcription
            logger.info(f"Using Twilio transcription: {query}")
        else:
            # Save audio to temporary file for speech recognition
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
                temp_audio.write(audio_response.content)
                temp_audio_path = temp_audio.name
            
            try:
                # Transcribe audio using speech_recognition
                recognizer = sr.Recognizer()
                with sr.AudioFile(temp_audio_path) as source:
                    audio = recognizer.record(source)
                    query = recognizer.recognize_google(audio)
                logger.info(f"Speech recognition result: {query}")
            except sr.UnknownValueError:
                logger.warning("Could not understand audio")
                response = VoiceResponse()
                response.say("I'm sorry, I couldn't understand what you said. Could you please call back and speak more clearly?", voice='alice')
                return str(response)
            except Exception as e:
                logger.error(f"Speech recognition error: {e}")
                query = "I'm having trouble understanding the audio quality."
            finally:
                # Clean up temporary file
                if os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
        
        # Generate AI response using Gemini
        logger.info(f"Generating AI response for: {query}")
        
        # Enhanced prompt for receptionist context
        enhanced_prompt = f"""
        You are a professional AI receptionist. A caller has asked: "{query}"
        
        Please provide a helpful, concise, and professional response. Keep your answer under 200 words and be friendly but professional. 
        If you cannot answer the specific question, politely explain what information you'd need or suggest they contact a human representative.
        """
        
        ai_response = model.generate_content(enhanced_prompt)
        response_text = ai_response.text
        
        logger.info(f"AI response generated: {response_text[:100]}...")
        
        # Create TwiML response with the AI-generated text
        twiml_response = VoiceResponse()
        twiml_response.say(response_text, voice='alice', language='en')
        
        # Offer additional help
        twiml_response.say("Is there anything else I can help you with today? Please call again if you have more questions. Thank you!", voice='alice')
        
        return str(twiml_response)
        
    except Exception as e:
        logger.error(f"Error processing voice: {e}")
        response = VoiceResponse()
        response.say("I'm sorry, I'm experiencing technical difficulties. Please try calling again later.", voice='alice')
        return str(response)
# SocketIO event for handling voice input from web interface
@socketio.on('voice_input')
def handle_voice_input(audio_data):
    """Handle voice input from web interface"""
    temp_audio_path = None
    try:
        logger.info("Processing web voice input...")
        
        # Convert base64 audio to WAV
        audio_bytes = base64.b64decode(audio_data)
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_audio:
            temp_audio.write(audio_bytes)
            temp_audio_path = temp_audio.name
        
        # Transcribe audio to text
        recognizer = sr.Recognizer()
        with sr.AudioFile(temp_audio_path) as source:
            audio = recognizer.record(source)
            query = recognizer.recognize_google(audio)
        
        logger.info(f"Web transcription result: {query}")
        
        # Enhanced prompt for web interface
        enhanced_prompt = f"""
        You are a helpful AI assistant. A user has asked: "{query}"
        
        Please provide a helpful, informative, and friendly response. Be conversational and engaging.
        """
        
        # Send query to Gemini
        response = model.generate_content(enhanced_prompt)
        response_text = response.text
        
        logger.info(f"Web AI response generated: {response_text[:100]}...")
        
        # Convert response to speech
        tts = gTTS(text=response_text, lang='en')
        audio_buffer = io.BytesIO()
        tts.write_to_fp(audio_buffer)
        audio_buffer.seek(0)
        audio_base64 = base64.b64encode(audio_buffer.read()).decode('utf-8')
        
        # Send response back to client
        socketio.emit('voice_response', {
            'text': response_text,
            'audio': audio_base64
        })
        
    except sr.UnknownValueError:
        logger.warning("Could not understand web audio input")
        socketio.emit('error', 'Could not understand the audio. Please try speaking more clearly.')
    except sr.RequestError as e:
        logger.error(f"Speech recognition service error: {e}")
        socketio.emit('error', 'Speech recognition service is unavailable.')
    except Exception as e:
        logger.error(f"Error processing web voice input: {e}")
        socketio.emit('error', f'An error occurred: {str(e)}')
    finally:
        # Clean up temporary file
        if temp_audio_path and os.path.exists(temp_audio_path):
            try:
                os.unlink(temp_audio_path)
            except Exception as e:
                logger.warning(f"Could not delete temporary file {temp_audio_path}: {e}")

# Add health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'gemini': bool(GEMINI_API_KEY),
            'twilio': bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
        }
    }

if __name__ == '__main__':
    socketio.run(app, debug=True)
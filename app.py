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
import json
from datetime import datetime
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Record, Start, Stream
from twilio.rest import Client
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Initialize Flask and SocketIO
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'fallback-secret-key')
socketio = SocketIO(app, cors_allowed_origins="*")

# Configure logging with UTF-8 encoding for Windows compatibility
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ai_receptionist.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
# Force stdout to UTF-8 for emoji support on Windows
import sys
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None
logger = logging.getLogger(__name__)

# Store conversation history per call (in-memory)
# In production, use Redis or a database
conversation_memory = {}

# Load and configure APIs
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000')  # Your ngrok or public URL

if not GEMINI_API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables")
    raise ValueError("GEMINI_API_KEY is required")

genai.configure(api_key=GEMINI_API_KEY)

# Initialize Twilio client
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    logger.info("Twilio client initialized successfully")
else:
    twilio_client = None
    logger.warning("Twilio credentials not found - phone functionality will be limited")

# Configure Gemini model (use gemini-2.0-flash for speed and reliability)
model = genai.GenerativeModel('gemini-2.0-flash')

# Home route
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process_gather', methods=['GET', 'POST'])  
def process_gather():
    """Process the gathered speech input from Twilio"""
    logger.info("Processing gathered speech input...")
    
    # Log the request for debugging
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request values: {dict(request.values)}")
    
    # Extract speech transcription from Twilio
    speech_result = request.values.get('SpeechResult')
    confidence = request.values.get('Confidence')
    call_sid = request.values.get('CallSid')
    
    logger.info(f"Speech result: {speech_result}")
    logger.info(f"Confidence: {confidence}")
    logger.info(f"Call SID: {call_sid}")
    
    response = VoiceResponse()
    
    if speech_result:
        # Check if user wants to end the call
        end_call_phrases = ['goodbye', 'bye', 'thank you bye', 'that\'s all', 'thats all', 'no more questions', 'i\'m done', 'im done', 'end call', 'hang up']
        
        if any(phrase in speech_result.lower() for phrase in end_call_phrases):
            logger.info("User requested to end call")
            # Clear conversation memory
            if call_sid in conversation_memory:
                del conversation_memory[call_sid]
            response.say("Thank you for calling! Have a wonderful day. Goodbye!")
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # Process speech with AI
        logger.info(f"Processing speech: {speech_result}")
        
        # Get conversation history for context
        history = conversation_memory.get(call_sid, [])
        
        # Build context from conversation history
        context = ""
        if history:
            context = "Previous conversation:\n"
            for turn in history[-3:]:  # Last 3 turns for context
                context += f"Customer: {turn['customer']}\nYou: {turn['assistant']}\n"
            context += "\n"
        
        # Generate AI response with conversation context
        enhanced_prompt = f"""{context}Customer just said: "{speech_result}"

Answer briefly in 2-3 sentences, being helpful and conversational. Remember the context from previous messages."""
        
        try:
            # Generate with faster settings
            generation_config = {
                "temperature": 0.7,
                "max_output_tokens": 100,  # Limit tokens for faster response
            }
            
            ai_response = model.generate_content(
                enhanced_prompt,
                generation_config=generation_config
            )
            response_text = ai_response.text
            
            logger.info(f"AI response generated: {response_text[:100]}...")
            
            # Store in conversation memory
            conversation_memory[call_sid].append({
                'customer': speech_result,
                'assistant': response_text
            })
            logger.info(f"Stored conversation turn for call {call_sid}. Total turns: {len(conversation_memory[call_sid])}")
            
            # Put AI response AND follow-up question inside Gather for interruption
            gather = Gather(
                input='speech',
                action=f'{BASE_URL}/process_gather',
                method='POST',
                timeout=3,  # Shorter timeout
                speech_timeout='auto',
                barge_in=True,  # Allow interruption during AI response
                partial_result_callback=f'{BASE_URL}/partial_result',
                partial_result_callback_method='POST'
            )
            # AI response is now INSIDE Gather - can be interrupted!
            gather.say(response_text, voice='Polly.Joanna')
            gather.say("Anything else?", voice='Polly.Joanna')
            response.append(gather)
            
            # If no more input, end call
            response.say("Thank you for calling. Have a great day!")
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            response.say("I'm sorry, I'm having trouble processing your request. Please try calling again.")
    
    else:
        # No input received
        response.say("I didn't receive any input. Thank you for calling. Goodbye!")
    
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/partial_result', methods=['POST'])
def partial_result():
    """Handle partial speech results for better interruption"""
    partial_text = request.values.get('UnstableSpeechResult', '')
    call_sid = request.values.get('CallSid')
    
    logger.info(f"Partial result for call {call_sid}: {partial_text}")
    
    # Return empty response to continue listening
    return '', 200

@app.route('/voice', methods=['GET', 'POST'])
def voice():
    """Handle incoming Twilio voice calls with Media Streams for interruption"""
    logger.info("Incoming Twilio voice call received")
    
    # Log the request method and parameters for debugging
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request values: {dict(request.values)}")
    
    # Get call details
    call_sid = request.values.get('CallSid')
    call_from = request.values.get('From') 
    call_to = request.values.get('To')
    
    logger.info(f"Call logged - SID: {call_sid}, From: {call_from}, To: {call_to}")
    
    # Initialize conversation memory for this call
    if call_sid not in conversation_memory:
        conversation_memory[call_sid] = []
        logger.info(f"Initialized conversation memory for call {call_sid}")
    
    # Create TwiML response
    response = VoiceResponse()
    
    # NOTE: Real-time WebSocket interruption requires a raw WebSocket server
    # Flask-SocketIO uses Socket.IO protocol which is incompatible with Twilio Media Streams
    # For production interruption, use: websockets library with asyncio, or FastAPI with WebSockets
    # Current implementation uses standard Gather which allows barge-in during prompts
    
    logger.info(f"Starting call with barge-in enabled on Gather")
    
    # Initial greeting with Gather (with bargeIn to allow interruption)
    gather = Gather(
        input='speech',
        action=f'{BASE_URL}/process_gather',
        method='POST',
        timeout=3,
        speech_timeout='auto',
        barge_in=True,  # Allow customer to interrupt AI speech
        partial_result_callback=f'{BASE_URL}/partial_result',
        partial_result_callback_method='POST'
    )
    gather.say("Hello! I'm your AI receptionist. How can I help you?", voice='Polly.Joanna')
    response.append(gather)
    
    # If no input, thank and hangup
    response.say("I didn't receive any input. Thank you for calling. Goodbye!")
    
    return str(response), 200, {'Content-Type': 'text/xml'}

@app.route('/process_voice', methods=['GET', 'POST'])
def process_voice():
    """Process the recorded voice message and generate AI response for Twilio"""
    logger.info("Processing Twilio voice recording...")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request values: {dict(request.values)}")
    
    # Log Twilio credential status for debugging
    logger.info(f"Twilio credentials available: {bool(twilio_client)}")
    
    response = VoiceResponse()
    
    try:
        # Twilio sends recording URL in RecordingUrl parameter
        recording_url = request.values.get('RecordingUrl')
        call_sid = request.values.get('CallSid')
        
        logger.info(f"Call SID: {call_sid}")
        logger.info(f"Recording URL: {recording_url}")
        
        if not recording_url:
            logger.error("No recording URL provided by Twilio")
            response.say("I'm sorry, I didn't receive your recording. Please try calling again.")
            return str(response), 200, {'Content-Type': 'text/xml'}
        
        # Download the audio file from Twilio using authentication
        try:
            # Check if we have Twilio credentials
            if not twilio_client:
                logger.error("Twilio credentials not configured")
                response.say("I'm sorry, there was a technical issue. Please try calling again.")
                return str(response), 200, {'Content-Type': 'text/xml'}
            
            # Download recording using Twilio authentication
            auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            audio_response = requests.get(recording_url, auth=auth)
            
            if audio_response.status_code != 200:
                logger.error(f"Failed to download Twilio recording: {audio_response.status_code}")
                logger.error(f"Recording URL: {recording_url}")
                logger.error(f"Response content: {audio_response.text[:500]}")
                response.say("I'm sorry, there was a technical issue. Please try calling again.")
                return str(response), 200, {'Content-Type': 'text/xml'}
                
        except Exception as download_error:
            logger.error(f"Exception downloading Twilio recording: {download_error}")
            response.say("I'm sorry, there was a technical issue. Please try calling again.")
            return str(response), 200, {'Content-Type': 'text/xml'}
        
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
            logger.info(f"Twilio speech recognition result: {query}")
        except sr.UnknownValueError:
            logger.warning("Could not understand audio from Twilio call")
            query = "I couldn't understand the audio clearly"
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            query = "I'm having trouble understanding the audio quality"
        finally:
            # Clean up temporary file
            if os.path.exists(temp_audio_path):
                os.unlink(temp_audio_path)
        
        # Generate AI response using Gemini
        logger.info(f"Generating AI response for Twilio call: {query}")
        
        # Enhanced prompt for receptionist context
        enhanced_prompt = f"""
        You are a professional AI receptionist. A caller has asked: "{query}"
        
        Please provide a helpful, concise, and professional response. 
        Keep your answer under 200 words and be friendly but professional. 
        If you cannot answer the specific question, politely explain what information you'd need or suggest they contact a human representative.
        """
        
        ai_response = model.generate_content(enhanced_prompt)
        response_text = ai_response.text
        
        logger.info(f"AI response for Twilio generated: {response_text[:100]}...")
        
        # Create TwiML response with the AI-generated text
        response.say(response_text)
        response.say("Is there anything else I can help you with today? Please call again if you have more questions. Thank you!")
        
        logger.info("Returning AI response TwiML")
        return str(response), 200, {'Content-Type': 'text/xml'}
        
    except Exception as e:
        logger.error(f"Error processing Twilio voice: {e}")
        response.say("I'm sorry, I'm experiencing technical difficulties. Please try calling again later.")
        return str(response), 200, {'Content-Type': 'text/xml'}
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

# NOTE: WebSocket Media Streams not compatible with Flask-SocketIO
# Flask-SocketIO uses Socket.IO protocol, Twilio Media Streams require raw WebSocket
# We use barge_in=True on Gather for excellent interruption support
# See INTERRUPTION_EXPLAINED.md for full details

# Add health check endpoint
@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'services': {
            'gemini': bool(GEMINI_API_KEY),
            'twilio': bool(twilio_client)
        },
        'active_conversations': len(conversation_memory),
        'interruption_method': 'barge_in (Gather)',
        'websocket_media_streams': 'not_supported_with_flask_socketio'
    }

# Add endpoint to view conversation memory (for debugging)
@app.route('/conversations')
def view_conversations():
    """View active conversation memories (for debugging)"""
    return {
        'active_calls': len(conversation_memory),
        'conversations': {
            call_sid: {
                'turns': len(history),
                'last_turn': history[-1] if history else None
            }
            for call_sid, history in conversation_memory.items()
        }
    }

if __name__ == '__main__':
    socketio.run(app, debug=True)
# AI Receptionist

A professional AI-powered receptionist that can handle phone calls through Exotel (Indian VoIP service) and provide intelligent responses using Google's Gemini AI. The system supports both phone calls and web-based voice interactions.

## Features

- 📞 **Phone Call Handling**: Receive and process incoming phone calls via Exotel (Indian numbers)
- 🎤 **Voice Recognition**: Convert speech to text using Google Speech Recognition
- 🤖 **AI Responses**: Generate intelligent responses using Google Gemini AI
- 🔊 **Text-to-Speech**: Convert AI responses back to speech
- 🌐 **Web Interface**: Browser-based voice interaction for testing
- 📝 **Logging**: Comprehensive logging for debugging and monitoring
- 🔐 **Secure**: Environment variable-based configuration for API keys
- 🇮🇳 **India-Optimized**: Uses Exotel for better connectivity and lower costs in India

## Prerequisites

- Python 3.8 or higher
- Exotel account with Indian phone number
- Google Cloud account with Gemini API access
- Internet connection for API calls

## Installation

1. **Clone or download this project**
   ```powershell
   cd "c:\Users\Ravi Ray\Documents\assistant"
   ```

2. **Install dependencies**
   ```powershell
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   - Copy the `.env` file and update it with your actual API keys:
   - Get your Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
   - Get your Twilio credentials from [Twilio Console](https://console.twilio.com/)
   
   Update `.env` file:
   ```
   GEMINI_API_KEY=your_actual_gemini_api_key
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token
   SECRET_KEY=your_secure_secret_key
   TWILIO_PHONE_NUMBER=your_twilio_phone_number
   ```

## Running the Application

### For Development (Local Testing)

1. **Start the Flask application**
   ```powershell
   python app.py
   ```

2. **Test the web interface**
   - Open your browser to `http://localhost:5000`
   - Click "Start Recording" to test voice interaction

3. **For phone testing, you'll need to expose your local server**
   - Install ngrok: `pip install pyngrok` or download from [ngrok.com](https://ngrok.com/)
   - Run ngrok: `ngrok http 5000`
   - Update your Twilio webhook URL to: `https://your-ngrok-url.ngrok.io/voice`

### For Production

1. **Deploy to a cloud service** (Heroku, DigitalOcean, AWS, etc.)
2. **Configure HTTPS** (required for Twilio webhooks)
3. **Set environment variables** in your cloud platform
4. **Update Twilio webhook URLs** to point to your production domain

## Twilio Configuration

1. **Log into Twilio Console**
2. **Go to Phone Numbers → Manage → Active numbers**
3. **Click on your phone number**
4. **Set the webhook URL for voice calls**:
   - Webhook URL: `https://your-domain.com/voice`
   - HTTP Method: POST
5. **Save the configuration**

## API Endpoints

- `GET /` - Web interface for testing
- `POST /voice` - Twilio webhook for incoming calls
- `POST /process_voice` - Processes recorded voice messages
- `GET /health` - Health check endpoint

## Customization

### Modifying the Greeting Message
Edit the greeting in `/voice` route in `app.py`:
```python
greeting = """Hello! You've reached our AI receptionist. 
I'm here to help you with any questions you may have."""
```

### Adjusting AI Behavior
Modify the prompts in the `process_voice` function to customize how the AI responds:
```python
enhanced_prompt = f"""
You are a professional AI receptionist for [Your Company]. 
A caller has asked: "{query}"
...
"""
```

### Recording Settings
Adjust recording parameters in the `/voice` route:
```python
response.record(
    max_length=30,  # Maximum recording length in seconds
    timeout=5,      # Silence timeout
    play_beep=True  # Play beep before recording
)
```

## Troubleshooting

### Common Issues

1. **"GEMINI_API_KEY not found"**
   - Make sure your `.env` file is in the same directory as `app.py`
   - Verify the API key is correctly set in `.env`

2. **Twilio webhooks not working**
   - Ensure your server is accessible from the internet (use ngrok for testing)
   - Check that webhook URLs in Twilio console are correct
   - Verify HTTPS is enabled (required for production)

3. **Audio quality issues**
   - Check microphone permissions in browser
   - Ensure stable internet connection
   - Verify audio format compatibility

4. **Speech recognition errors**
   - Speak clearly and avoid background noise
   - Check internet connection for Google Speech API
   - Consider using Twilio's built-in transcription as fallback

### Logs

Check the `ai_receptionist.log` file for detailed error messages and debugging information.

## Security Notes

- Never commit API keys to version control
- Use environment variables for all sensitive configuration
- Enable HTTPS in production
- Regularly rotate API keys and secrets
- Monitor usage and costs for AI API calls

## Cost Considerations

- **Twilio**: Charges per minute for phone calls and per transcription
- **Google Gemini**: Charges per API request based on usage
- **Google Speech Recognition**: Charges per minute of audio processed
- **Google Text-to-Speech**: Charges per character synthesized

Monitor your usage through respective service dashboards.

## License

This project is for educational and demonstration purposes. Please ensure compliance with all service terms of use.
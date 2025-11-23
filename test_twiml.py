"""
Test script to verify TwiML structure for interruption
Run this to see the exact XML being generated
"""

from twilio.twiml.voice_response import VoiceResponse, Gather

# Simulate the FIXED code (interruption works)
def test_with_interruption():
    print("=" * 60)
    print("FIXED VERSION - Interruption WORKS ✅")
    print("=" * 60)
    
    response = VoiceResponse()
    
    # AI response INSIDE Gather
    gather = Gather(
        input='speech',
        action='https://example.com/process_gather',
        method='POST',
        timeout=3,
        speech_timeout='auto',
        barge_in=True,  # Enable interruption
    )
    
    # Both AI response AND follow-up inside Gather
    gather.say("I'm doing well, thank you for asking! I hope you're having a good day too. How can I help you today?", voice='Polly.Joanna')
    gather.say("Anything else?", voice='Polly.Joanna')
    
    response.append(gather)
    response.say("Thank you for calling. Have a great day!")
    
    print(str(response))
    print()


# Simulate the BROKEN code (interruption doesn't work)
def test_without_interruption():
    print("=" * 60)
    print("BROKEN VERSION - Interruption DOESN'T WORK ❌")
    print("=" * 60)
    
    response = VoiceResponse()
    
    # AI response OUTSIDE Gather - cannot interrupt!
    response.say("I'm doing well, thank you for asking! I hope you're having a good day too. How can I help you today?", voice='Polly.Joanna')
    
    # Only this tiny part inside Gather
    gather = Gather(
        input='speech',
        action='https://example.com/process_gather',
        method='POST',
        timeout=3,
        speech_timeout='auto',
        barge_in=True,
    )
    gather.say("Anything else?", voice='Polly.Joanna')
    
    response.append(gather)
    response.say("Thank you for calling. Have a great day!")
    
    print(str(response))
    print()


if __name__ == '__main__':
    # Show broken version first
    test_without_interruption()
    
    print("\n" + "🔄" * 30 + "\n")
    
    # Show fixed version
    test_with_interruption()
    
    print("\n" + "=" * 60)
    print("KEY DIFFERENCE:")
    print("=" * 60)
    print("❌ BROKEN: <Say> before <Gather> - cannot interrupt AI response")
    print("✅ FIXED: <Say> inside <Gather> - can interrupt AI response")
    print("=" * 60)

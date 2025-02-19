import os
import logging
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse
from flask import Flask, request
from bot import MayaBot
from config import Config

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)

# Initialize Maya bot
maya = MayaBot()

def send_sms(to_number: str, message: str) -> None:
    """Send SMS using Twilio client"""
    try:
        client = Client(
            os.environ.get('TWILIO_ACCOUNT_SID'),
            os.environ.get('TWILIO_AUTH_TOKEN')
        )
        
        message = client.messages.create(
            body=message,
            from_=os.environ.get('TWILIO_PHONE_NUMBER'),
            to=to_number
        )
        logger.info(f"Message sent: {message.sid}")
    except Exception as e:
        logger.error(f"Error sending SMS: {str(e)}")

@app.route("/sms", methods=['POST'])
def sms_reply():
    """Handle incoming SMS messages"""
    try:
        # Get incoming message
        incoming_msg = request.values.get('Body', '').strip()
        sender = request.values.get('From', '')

        # Get Maya's response
        response = maya.handle_message(incoming_msg)

        # Create TwiML response
        resp = MessagingResponse()
        resp.message(response)

        return str(resp)
    except Exception as e:
        logger.error(f"Error processing SMS: {str(e)}")
        return str(MessagingResponse().message("Sorry, I'm having trouble processing your message."))

def main():
    """Start the Flask server"""
    # Verify required environment variables
    required_vars = ['TWILIO_ACCOUNT_SID', 'TWILIO_AUTH_TOKEN', 'TWILIO_PHONE_NUMBER']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        return

    # Start Flask server
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main()

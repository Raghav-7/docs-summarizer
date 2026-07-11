import os
import re
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def parse_whatsapp_chat(file_path):
    """
    Parses a WhatsApp exported chat text file.
    Supports standard Android and iOS export formats.
    """
    parsed_messages = []
    
    # Common WhatsApp export formats:
    # Android: 14/08/23, 10:20 - John Doe: Hello
    # iOS: [14/08/23, 10:20:15] John Doe: Hello
    pattern = re.compile(
        r'\[?(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[aApP][mM])?)\]?\s?-?\s?(?P<sender>[^:]+):\s?(?P<message>.*)'
    )
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                match = pattern.match(line)
                if match:
                    parsed_messages.append({
                        'date': match.group('date'),
                        'time': match.group('time'),
                        'sender': match.group('sender'),
                        'message': match.group('message')
                    })
    except FileNotFoundError:
        print(f"Error: The file {file_path} was not found.")
        return None
        
    return parsed_messages

def summarize_chat(messages):
    """
    Uses Gemini API to summarize the parsed messages.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in environment or .env file.")
        print("Please create a .env file with your API key from Google AI Studio.")
        return
        
    genai.configure(api_key=api_key)
    
    # Format messages for the prompt
    formatted_chat = ""
    for msg in messages:
        formatted_chat += f"[{msg['date']} {msg['time']}] {msg['sender']}: {msg['message']}\n"
        
    if not formatted_chat:
        print("No valid messages found to summarize.")
        return

    # Use the gemini-flash-latest model
    model = genai.GenerativeModel('gemini-flash-latest')
    
    prompt = f"""
    Please provide a comprehensive summary of the following WhatsApp group chat. 
    Highlight the main topics discussed, any key decisions made, and any action items assigned to specific people.
    
    Chat Log:
    {formatted_chat}
    """
    
    print("Sending to Gemini for summarization...")
    try:
        response = model.generate_content(prompt)
        print("\n=== SUMMARY ===\n")
        print(response.text)
        print("\n===============\n")
    except Exception as e:
        print(f"An error occurred during summarization: {e}")

if __name__ == "__main__":
    chat_file = "chat.txt" # Ensure your file is named chat.txt or change this path
    
    print("Parsing WhatsApp chat...")
    messages = parse_whatsapp_chat(chat_file)
    
    if messages:
        print(f"Successfully parsed {len(messages)} messages.")
        # Uncomment the line below to test summarization once you have your API key in a .env file
        summarize_chat(messages)
        
        # For local testing, we just print the first few parsed messages
        print("\nSample parsed messages:")
        for msg in messages[:3]:
            print(msg)

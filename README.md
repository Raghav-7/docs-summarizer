# WhatsApp Groupchat Summarizer

A Python tool that automatically parses exported WhatsApp group chats and generates a concise summary using the Google Gemini AI.

## Prerequisites
1. **Python**: Ensure Python is installed on your computer.
2. **API Key**: You need a free Gemini API key from [Google AI Studio](https://aistudio.google.com/).

## Setup Instructions
1. Install the required dependencies by opening a terminal in this folder and running:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a file named `.env` in this directory (if it doesn't already exist) and add your API key like this:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   ```

## How to Use the Summarizer
1. **Export your WhatsApp Chat:**
   - Open WhatsApp on your phone.
   - Go to the group chat you want to summarize.
   - Tap the group name at the top -> Scroll down to **"Export Chat"**.
   - Select **"Without Media"**.
   - Transfer the resulting `.txt` file to your computer.

2. **Prepare the File:**
   - Rename your exported chat file to `chat.txt`.
   - Place it inside this `whatsapp-summary` folder (replacing the dummy `chat.txt` if it's there).

3. **Run the Script:**
   - Open a terminal/command prompt in this folder.
   - Run the following command:
     ```bash
     python summarize.py
     ```
   - Wait a few seconds, and the AI-generated summary will print directly to your terminal, highlighting the main topics, key decisions, and action items!

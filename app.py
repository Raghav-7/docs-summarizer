import os
import re
import io
import html as html_module
import tempfile
import zipfile
import shutil
import mimetypes
import requests as http_requests
import itertools
from functools import wraps
from flask import Flask, request, jsonify, render_template, session, redirect, url_for, flash, send_file
from fpdf import FPDF
from flask_sqlalchemy import SQLAlchemy
import google.generativeai as genai
from datetime import datetime, date
import sys
import shutil
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

TEMP_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), 'temp_uploads')
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
import emoji
import uuid

# ─── Tool Registry ────────────────────────────────────────────────
TOOLS = {
    'summarize': {
        'title': 'Summarize Chat',
        'description': 'Get a concise AI-powered summary of any WhatsApp group chat.',
        'long_description': 'Upload your exported WhatsApp chat and get a comprehensive summary highlighting main topics, key decisions, and action items.',
        'icon': 'summarize',
        'color': '#4f46e5',
        'prompt': 'Please provide a comprehensive summary of the following WhatsApp group chat. Highlight the main topics discussed, key decisions, and action items.',
        'accepts': '.txt,.zip',
        'show_stats': True,
        'show_profiles': True,
    },
    'action-items': {
        'title': 'Extract Action Items',
        'description': 'Pull out every task, decision, and deadline from your chat.',
        'long_description': 'Automatically identify and list all action items, assigned tasks, deadlines, and key decisions made in the conversation.',
        'icon': 'action',
        'color': '#059669',
        'prompt': 'Analyze the following WhatsApp group chat and extract ALL action items, tasks, deadlines, and decisions. Format the output as a clear, organized list grouped by person responsible (if identifiable). For each item, note the date it was mentioned and any deadline if specified.',
        'accepts': '.txt,.zip',
        'show_stats': False,
        'show_profiles': False,
    },
    'statistics': {
        'title': 'Chat Statistics',
        'description': 'Visualize message counts, activity timelines, and emoji usage.',
        'long_description': 'Get detailed analytics about your group chat — who talks most, when the group is most active, top emojis, shared links, and more.',
        'icon': 'stats',
        'color': '#d97706',
        'prompt': 'Provide a brief 2-3 sentence overview of this WhatsApp group chat dynamics, mentioning who the most active members are and what the group seems to be about.',
        'accepts': '.txt,.zip',
        'show_stats': True,
        'show_profiles': False,
    },
    'sentiment': {
        'title': 'Sentiment Analysis',
        'description': 'Track the mood and tone of your group over time.',
        'long_description': 'Analyze the emotional tone of the conversation. Find out if the group mood was positive, negative, or neutral, and how it changed over time.',
        'icon': 'sentiment',
        'color': '#db2777',
        'prompt': 'Analyze the sentiment of the following WhatsApp group chat. For each major participant, rate their overall tone as Positive, Neutral, or Negative with a percentage. Then provide a timeline of how the group mood shifted across different dates/topics. Use this format:\n\n**Overall Group Mood:** [Positive/Neutral/Negative]\n\n**Per-Person Sentiment:**\n- [Name]: [Mood] ([percentage]%) — [1-line explanation]\n\n**Mood Timeline:**\n- [Date/Topic]: [Mood shift explanation]',
        'accepts': '.txt,.zip',
        'show_stats': False,
        'show_profiles': False,
    },
    'search': {
        'title': 'Search Chat',
        'description': 'Ask questions about your chat and get instant answers.',
        'long_description': 'Upload your chat and ask any question — "When did we discuss the trip?", "What restaurant did John recommend?". The AI finds the answer instantly.',
        'icon': 'search',
        'color': '#2563eb',
        'prompt': 'You are a helpful assistant. The user has uploaded a WhatsApp chat log. Read it carefully and be ready to answer any questions about its contents. Start by providing a brief 2-3 sentence overview of what this chat is about, then say "Ask me anything about this chat!"',
        'accepts': '.txt,.zip',
        'show_stats': False,
        'show_profiles': False,
    },
    'export': {
        'title': 'Export Report',
        'description': 'Generate a beautiful PDF report with summary and analytics.',
        'long_description': 'Create a professional, downloadable PDF report combining the AI summary, chat statistics, personality profiles, and key insights — perfect for sharing.',
        'icon': 'export',
        'color': '#475569',
        'prompt': 'Please provide a comprehensive, well-structured summary of the following WhatsApp group chat. Use clear headings and bullet points. Highlight the main topics discussed, key decisions, action items, and notable moments. Then, on a new line, write exactly \'|||PROFILES|||\' and after that provide a 1-sentence funny personality profile for the top 5 most active users in this chat.',
        'accepts': '.txt,.zip,.pdf',
        'show_stats': True,
        'show_profiles': True,
    },
}

# ─── Global session store for chat ────────────────────────────────
ACTIVE_SESSIONS = {}

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)

# Security setup
app.secret_key = os.getenv('APP_SECRET_KEY', 'default_secret_key_if_env_missing')

# Configure SQLite Database
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'database.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024 # Limit uploads to 100MB

db = SQLAlchemy(app)

# Load API Keys — supports comma-separated keys for rotation
GEMINI_API_KEYS = [k.strip() for k in os.getenv("GEMINI_API_KEY", "").split(',') if k.strip()]
GROQ_API_KEYS = [k.strip() for k in os.getenv("GROQ_API_KEY", "").split(',') if k.strip()]
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "Admin@007")

# Round-robin key iterators
_gemini_cycle = itertools.cycle(GEMINI_API_KEYS) if GEMINI_API_KEYS else None
_groq_cycle = itertools.cycle(GROQ_API_KEYS) if GROQ_API_KEYS else None

FREE_DAILY_LIMIT = 3

print(f"[Init] Loaded {len(GEMINI_API_KEYS)} Gemini key(s) and {len(GROQ_API_KEYS)} Groq key(s)")

def get_next_gemini_key():
    """Get the next API key in rotation."""
    if _gemini_cycle:
        return next(_gemini_cycle)
    return None

def get_next_groq_key():
    """Get the next Groq API key in rotation."""
    if _groq_cycle:
        return next(_groq_cycle)
    return None

def call_gemini_with_retry(prompt_contents, max_retries=None):
    """Try each Gemini key; on 429/error rotate to next. Falls back to Groq if all fail."""
    if max_retries is None:
        max_retries = len(GEMINI_API_KEYS) if GEMINI_API_KEYS else 1
    
    last_error = None
    for attempt in range(max_retries):
        api_key = get_next_gemini_key()
        if not api_key:
            break
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-flash-lite-latest')
            chat_session = model.start_chat(history=[])
            response = chat_session.send_message(prompt_contents)
            return response.text, chat_session, 'gemini'
        except Exception as e:
            last_error = e
            error_str = str(e)
            if '429' in error_str or 'quota' in error_str.lower() or 'rate' in error_str.lower():
                print(f"[Key Rotation] Gemini key {attempt+1}/{max_retries} rate-limited, trying next...")
                continue
            else:
                raise  # Non-rate-limit errors should fail immediately
    
    # All Gemini keys exhausted — try Groq fallback
    print(f"DEBUG: Gemini failed. Last error: {last_error}")
    if GROQ_API_KEYS:
        print("[Fallback] All Gemini keys exhausted. Using Groq...")
        return call_groq_fallback(prompt_contents)
    
    raise Exception(f"All API keys exhausted. Last error: {last_error}")

def call_groq_fallback(prompt_contents):
    """Use Groq's free Llama model as a fallback. Rotates through multiple Groq keys."""
    # Extract text from prompt_contents (skip file objects)
    text_parts = [p for p in prompt_contents if isinstance(p, str)]
    combined_prompt = "\n".join(text_parts)
    
    # Truncate for Groq to prevent token limit errors
    max_chars = 40000
    if len(combined_prompt) > max_chars:
        print(f"[WARNING] Truncating prompt for Groq fallback (was {len(combined_prompt)} chars).")
        combined_prompt = combined_prompt[:2000] + "\n...[CONTENT TRUNCATED]...\n" + combined_prompt[-38000:]
    
    max_retries = len(GROQ_API_KEYS)
    for attempt in range(max_retries):
        groq_key = get_next_groq_key()
        if not groq_key:
            break
        try:
            response = http_requests.post(
                'https://api.groq.com/openai/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {groq_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'llama-3.3-70b-versatile',
                    'messages': [{'role': 'user', 'content': combined_prompt}],
                    'max_tokens': 4096
                },
                timeout=120
            )
            
            if response.status_code == 429:
                print(f"[Key Rotation] Groq key {attempt+1}/{max_retries} rate-limited, trying next...")
                continue
            
            if response.status_code != 200:
                raise Exception(f"Groq API error: {response.text}")
            
            result = response.json()
            return result['choices'][0]['message']['content'], None, 'groq'
        except Exception as e:
            if '429' in str(e) or 'rate' in str(e).lower():
                continue
            raise
    
    raise Exception("All Groq API keys exhausted.")

# ─── Database Models ──────────────────────────────────────────────
class Summary(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))
    content = db.Column(db.Text)
    tool_name = db.Column(db.String(50), default='summarize')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Usage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(db.String(45))
    use_date = db.Column(db.Date, default=date.today)
    count = db.Column(db.Integer, default=0)

# Create tables
with app.app_context():
    db.create_all()

# ─── Usage Limiter ────────────────────────────────────────────────
def get_usage_count():
    """Get today's usage count for current session."""
    uid = session.get('uid')
    if not uid: return 0
    today = date.today()
    usage = Usage.query.filter_by(ip_address=uid, use_date=today).first()
    return usage.count if usage else 0

def increment_usage():
    """Increment today's usage count for current session."""
    if 'uid' not in session:
        session['uid'] = str(uuid.uuid4())
    uid = session['uid']
    today = date.today()
    usage = Usage.query.filter_by(ip_address=uid, use_date=today).first()
    if usage:
        usage.count += 1
    else:
        usage = Usage(ip_address=uid, use_date=today, count=1)
        db.session.add(usage)
    db.session.commit()

def check_rate_limit():
    """Check if current user has exceeded free limit. Returns (allowed, remaining)."""
    if session.get('logged_in'):
        return True, 999  # Admin has unlimited
    if 'uid' not in session:
        session['uid'] = str(uuid.uuid4())
    used = get_usage_count()
    remaining = max(0, FREE_DAILY_LIMIT - used)
    return remaining > 0, remaining

# ─── Auth Decorator ───────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ─── Chat Parser ─────────────────────────────────────────────────
def parse_chat(text):
    lines = text.split('\n')
    parsed_messages = []
    stats = {}
    time_series = {}
    hourly_activity = {str(i).zfill(2): {} for i in range(24)}
    media_stats = {'stickers': 0, 'gifs': 0, 'links': 0, 'media_omitted': 0}
    emoji_counts = {}
    shared_links = {}
    url_pattern = re.compile(r'(https?://[^\s]+)')
    
    user_stats = {}
    monthly_activity = {str(i).zfill(2): {} for i in range(1, 13)}
    weekday_activity = {str(i): {} for i in range(7)}
    global_first_date = None
    global_last_date = None
    
    # Regex handles Android and iOS WhatsApp exports
    pattern = re.compile(
        r'\[?(?P<date>\d{1,2}/\d{1,2}/\d{2,4}),?\s(?P<time>\d{1,2}:\d{2}(?::\d{2})?(?:\s?[aApP][mM])?)\]?\s?-?\s?(?P<sender>[^:]+):\s?(?P<message>.*)'
    )
    
    for line in lines:
        match = pattern.match(line)
        if match:
            date_str = match.group('date')
            time = match.group('time')
            sender = match.group('sender').strip()
            message = match.group('message')
            
            if sender not in user_stats:
                user_stats[sender] = {'words': 0, 'unique_words': set(), 'longest': 0, 'emojis': {}}
                
            try:
                parts = re.split(r'[/.-]', date_str)
                if len(parts) == 3:
                    year = parts[2]
                    if len(year) == 2: year = "20" + year
                    p1, p2 = int(parts[0]), int(parts[1])
                    if p1 > 12: m, d = p2, p1
                    else: m, d = p1, p2
                    dt = date(int(year), m, d)
                    
                    if global_first_date is None or dt < global_first_date: global_first_date = dt
                    if global_last_date is None or dt > global_last_date: global_last_date = dt
                    
                    m_str = str(dt.month).zfill(2)
                    w_str = str(dt.weekday())
                    
                    monthly_activity[m_str][sender] = monthly_activity[m_str].get(sender, 0) + 1
                    weekday_activity[w_str][sender] = weekday_activity[w_str].get(sender, 0) + 1
                    iso_date = f"{year}-{str(m).zfill(2)}-{str(d).zfill(2)}"
                else:
                    iso_date = date_str
            except:
                iso_date = date_str
                
            time = match.group('time')
            
            # Media detection
            lower_msg = message.lower()
            if 'sticker omitted' in lower_msg:
                media_stats['stickers'] += 1
            elif 'gif omitted' in lower_msg:
                media_stats['gifs'] += 1
            elif 'image omitted' in lower_msg or 'video omitted' in lower_msg or 'audio omitted' in lower_msg:
                media_stats['media_omitted'] += 1
                
            # Emoji extraction
            emojis_in_msg = emoji.emoji_list(message)
            for e in emojis_in_msg:
                emoji_char = e['emoji']
                emoji_counts[emoji_char] = emoji_counts.get(emoji_char, 0) + 1
                user_stats[sender]['emojis'][emoji_char] = user_stats[sender]['emojis'].get(emoji_char, 0) + 1
                
            # Words extraction
            words = message.split()
            word_count = len(words)
            user_stats[sender]['words'] += word_count
            if word_count > user_stats[sender]['longest']:
                user_stats[sender]['longest'] = word_count
            for w in words:
                user_stats[sender]['unique_words'].add(w.lower())
                
            # URL extraction
            urls = url_pattern.findall(message)
            if urls:
                media_stats['links'] += len(urls)
            for url in urls:
                if url not in shared_links:
                    shared_links[url] = {'count': 0, 'senders': set()}
                shared_links[url]['count'] += 1
                shared_links[url]['senders'].add(sender)
            
            # Hourly activity
            try:
                hour_str = time.split(':')[0]
                if 'pm' in time.lower() and hour_str != '12':
                    hour_str = str(int(hour_str) + 12)
                elif 'am' in time.lower() and hour_str == '12':
                    hour_str = '00'
                hour_str = hour_str.zfill(2)
                if hour_str in hourly_activity:
                    hourly_activity[hour_str][sender] = hourly_activity[hour_str].get(sender, 0) + 1
            except:
                pass
            
            parsed_messages.append(f"[{date_str} {time}] {sender}: {message}")
            stats[sender] = stats.get(sender, 0) + 1
            
            if iso_date not in time_series:
                time_series[iso_date] = {}
            time_series[iso_date][sender] = time_series[iso_date].get(sender, 0) + 1
            
    # Sort stats by message count
    sorted_stats = dict(sorted(stats.items(), key=lambda item: item[1], reverse=True))
    
    # Sort emojis and get top 5
    sorted_emojis = dict(sorted(emoji_counts.items(), key=lambda item: item[1], reverse=True)[:5])
    
    # Sort links and get top 50, converting sets to lists
    sorted_links = {}
    for url, data in sorted(shared_links.items(), key=lambda x: x[1]['count'], reverse=True)[:50]:
        sorted_links[url] = {'count': data['count'], 'senders': list(data['senders'])}
    
    advanced_stats = {
        'kpis': {
            'first_date': global_first_date.isoformat() if global_first_date else None,
            'last_date': global_last_date.isoformat() if global_last_date else None,
            'days_chatted': (global_last_date - global_first_date).days + 1 if global_first_date and global_last_date else 0,
            'total_messages': len(parsed_messages),
            'people_count': len(stats)
        },
        'user_stats': {
            s: {
                'messages': stats[s],
                'words': u['words'],
                'unique_words': len(u['unique_words']),
                'longest': u['longest'],
                'avg_words': round(u['words'] / stats[s]) if stats[s] > 0 else 0,
                'top_emojis': dict(sorted(u['emojis'].items(), key=lambda x: x[1], reverse=True)[:5])
            }
            for s, u in user_stats.items()
        },
        'monthly': monthly_activity,
        'weekday': weekday_activity
    }
    
    return '\n'.join(parsed_messages), sorted_stats, time_series, hourly_activity, media_stats, sorted_emojis, sorted_links, advanced_stats


# ═══════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route('/')
def home():
    allowed, remaining = check_rate_limit()
    return render_template('home.html', tools=TOOLS, remaining=remaining, limit=FREE_DAILY_LIMIT)

@app.route('/tool/<tool_name>')
def tool_page(tool_name):
    if tool_name not in TOOLS:
        return redirect(url_for('home'))
    tool = TOOLS[tool_name]
    allowed, remaining = check_rate_limit()
    return render_template('tool.html', tool_name=tool_name, tool=tool, remaining=remaining, limit=FREE_DAILY_LIMIT)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USER and password == ADMIN_PASS:
            session['logged_in'] = True
            return redirect(url_for('history'))
        else:
            flash('Invalid username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/admin/history')
@login_required
def history():
    summaries = Summary.query.order_by(Summary.created_at.desc()).all()
    return render_template('history.html', summaries=summaries)

# ─── Unified Tool API ─────────────────────────────────────────────

@app.route('/api/tool/<tool_name>/stats', methods=['POST'])
def api_tool_stats(tool_name):
    if tool_name not in TOOLS:
        return jsonify({'error': 'Unknown tool'}), 400

    raw_text = request.form.get('raw_text')
    file = request.files.get('file')
    
    if not file and not raw_text:
        return jsonify({'error': 'No file uploaded or text provided'}), 400

    chat_text = ""
    is_document = False
    file_id = None
    
    try:
        if raw_text:
            chat_text = raw_text
        else:
            filename = file.filename
            file_id = str(uuid.uuid4())
            cached_path = os.path.join(TEMP_UPLOAD_DIR, file_id + '_' + secure_filename(filename))
            file.seek(0)
            file.save(cached_path)
            
            if filename.lower().endswith('.pdf'):
                is_document = True
            elif filename.lower().endswith('.zip'):
                with tempfile.TemporaryDirectory() as temp_dir:
                    with zipfile.ZipFile(cached_path, 'r') as zip_ref:
                        zip_ref.extractall(temp_dir)
                    for root, _, files in os.walk(temp_dir):
                        for f in files:
                            if f.endswith('.txt'):
                                full_path = os.path.join(root, f)
                                with open(full_path, 'r', encoding='utf-8') as txt_file:
                                    chat_text = txt_file.read()
            else:
                with open(cached_path, 'r', encoding='utf-8', errors='ignore') as f:
                    chat_text = f.read()
                
        if is_document:
            return jsonify({'is_document': True, 'file_id': file_id})
            
        formatted_chat, stats, time_series, hourly_activity, media_stats, top_emojis, shared_links, advanced_stats = parse_chat(chat_text)
        if not formatted_chat:
             return jsonify({'error': 'Could not parse any messages from the uploaded file.'}), 400
             
        return jsonify({
            'file_id': file_id,
            'is_document': False,
            'stats': stats,
            'time_series': time_series,
            'hourly_activity': hourly_activity,
            'media': media_stats,
            'emojis': top_emojis,
            'links': shared_links,
            'advanced_stats': advanced_stats
        })
    except Exception as e:
        print(f"Stats Error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/tool/<tool_name>', methods=['POST'])
def api_tool(tool_name):
    if tool_name not in TOOLS:
        return jsonify({'error': 'Unknown tool'}), 400

    # Rate limit check
    allowed, remaining = check_rate_limit()
    if not allowed:
        return jsonify({
            'error': f'You\'ve used all {FREE_DAILY_LIMIT} free analyses for today. Come back tomorrow or log in for unlimited access.',
            'limit_reached': True
        }), 429

    tool = TOOLS[tool_name]
    raw_text = request.form.get('raw_text')
    file = request.files.get('file')
    file_id = request.form.get('file_id')
    instruction = tool['prompt']
    
    if not file and not raw_text and not file_id:
        return jsonify({'error': 'No file uploaded, text provided, or file ID given'}), 400
        
    if file:
        file.seek(0, os.SEEK_END)
        file_length = file.tell()
        file.seek(0)
        # File size limits are now handled globally by MAX_CONTENT_LENGTH (250MB)
    
    prompt_contents = []
    uploaded_gemini_files = []
    
    chat_id = str(uuid.uuid4())
    is_document = False
    stats = {}
    time_series = {}
    media_stats = {}
    top_emojis = {}
    shared_links = {}
    
    try:
        if raw_text:
            filename = "Pasted Text"
            formatted_chat, stats, time_series, hourly_activity, media_stats, top_emojis, shared_links, advanced_stats = parse_chat(raw_text)
            if not formatted_chat:
                return jsonify({'error': 'Could not parse pasted text.'}), 400
            
            profiles_instruction = ""
            if tool.get('show_profiles'):
                profiles_instruction = " Then, on a new line, write exactly '|||PROFILES|||' and after that provide a 1-sentence funny personality profile for the top 5 most active users in this chat."
            
            prompt_contents.append(f"{instruction}{profiles_instruction}\n\nChat Log:\n{formatted_chat}")
            
        else:
            if file_id:
                cached_files = [f for f in os.listdir(TEMP_UPLOAD_DIR) if f.startswith(file_id + '_')]
                if not cached_files:
                    return jsonify({'error': 'Cached file not found. Please upload again.'}), 400
                cached_path = os.path.join(TEMP_UPLOAD_DIR, cached_files[0])
                filename = cached_files[0].split('_', 1)[1]
            else:
                filename = file.filename
                
            with tempfile.TemporaryDirectory() as temp_dir:
                file_path = os.path.join(temp_dir, filename)
                if file_id:
                    shutil.copy(cached_path, file_path)
                else:
                    file.save(file_path)
                
                if filename.lower().endswith('.pdf'):
                    is_document = True
                    upload_key = get_next_gemini_key()
                    if upload_key:
                        genai.configure(api_key=upload_key)
                    gemini_file = genai.upload_file(file_path)
                    uploaded_gemini_files.append(gemini_file)
                    prompt_contents.append(gemini_file)
                    prompt_contents.append("Please provide a comprehensive summary of this document. Highlight key findings, main ideas, and any important data points.")
                else:
                    # Handling zip or txt
                    chat_text = ""
                    if filename.lower().endswith('.zip'):
                        with zipfile.ZipFile(file_path, 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                        for root, _, files in os.walk(temp_dir):
                            for f in files:
                                full_path = os.path.join(root, f)
                                if f.endswith('.txt'):
                                    with open(full_path, 'r', encoding='utf-8') as txt_file:
                                        chat_text = txt_file.read()
                                elif f != file.filename:
                                    mime_type, _ = mimetypes.guess_type(full_path)
                                    if mime_type and (mime_type.startswith('image/') or mime_type.startswith('audio/') or mime_type.startswith('video/')):
                                        if GEMINI_API_KEYS:
                                            genai.configure(api_key=GEMINI_API_KEYS[0])
                                        try:
                                            gemini_file = genai.upload_file(full_path, mime_type=mime_type)
                                            uploaded_gemini_files.append(gemini_file)
                                        except Exception as e:
                                            print(f"Warning: Failed to upload media {f}: {e}")
                    else:
                        with open(file_path, 'r', encoding='utf-8') as txt_file:
                            chat_text = txt_file.read()
                            
                    formatted_chat, stats, time_series, hourly_activity, media_stats, top_emojis, shared_links, advanced_stats = parse_chat(chat_text)
                    if not formatted_chat:
                        return jsonify({'error': 'Could not parse any messages from the uploaded file.'}), 400
                    
                    profiles_instruction = ""
                    if tool.get('show_profiles'):
                        profiles_instruction = " Then, on a new line, write exactly '|||PROFILES|||' and after that provide a 1-sentence funny personality profile for the top 5 most active users in this chat."
                    
                    prompt_contents.append(f"{instruction}{profiles_instruction}\n\nChat Log:\n{formatted_chat}")
                    prompt_contents.extend(uploaded_gemini_files)
        
        full_text, chat_session, provider = call_gemini_with_retry(prompt_contents)
        if chat_session:
            ACTIVE_SESSIONS[chat_id] = chat_session

        if "|||PROFILES|||" in full_text:
            parts = full_text.split("|||PROFILES|||")
            summary_text = parts[0].strip()
            profiles_text = parts[1].strip()
        else:
            summary_text = full_text
            profiles_text = ""
        
        # Increment usage for free users
        if not session.get('logged_in'):
            increment_usage()
        
        # Admin Database Storage
        if session.get('logged_in'):
            new_summary = Summary(filename=filename, content=summary_text, tool_name=tool_name)
            db.session.add(new_summary)
            db.session.commit()
            
        return jsonify({
            'response': summary_text,
            'profiles': profiles_text,
            'chat_id': chat_id,
            'is_document': is_document,
            'stats': stats if tool.get('show_stats') else {},
            'time_series': time_series if tool.get('show_stats') else {},
            'hourly_activity': hourly_activity if tool.get('show_stats') else {},
            'media': media_stats,
            'emojis': top_emojis,
            'links': shared_links if not is_document else {},
            'remaining': max(0, (FREE_DAILY_LIMIT - get_usage_count()) if not session.get('logged_in') else 999)
        })
        
    except Exception as e:
        print(f"Tool API Error [{tool_name}]: {str(e)}")
        error_msg = str(e)
        if 'All API keys exhausted' in error_msg or '429' in error_msg or 'quota' in error_msg.lower():
            user_msg = "The AI service is currently receiving too many requests. Please try again in a few minutes."
        elif 'invalid' in error_msg.lower() and 'api key' in error_msg.lower():
            user_msg = "Our AI service configuration needs updating. Please contact the administrator."
        else:
            user_msg = "An unexpected error occurred while analyzing the chat. Please try again."
        return jsonify({'error': user_msg}), 500

# Keep legacy endpoint for backward compatibility
@app.route('/api/summarize', methods=['POST'])
def summarize():
    return api_tool('summarize')

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    chat_id = data.get('chat_id')
    message = data.get('message')
    
    if not chat_id or not message:
        return jsonify({'error': 'Missing chat_id or message'}), 400
        
    if chat_id not in ACTIVE_SESSIONS:
        return jsonify({'error': 'Chat session expired or not found. Please upload the file again.'}), 404
        
    chat_session = ACTIVE_SESSIONS[chat_id]
    try:
        response = chat_session.send_message(message)
        return jsonify({'response': response.text})
    except Exception as e:
        error_str = str(e)
        if '429' in error_str or 'quota' in error_str.lower():
            try:
                api_key = get_next_gemini_key()
                if api_key:
                    genai.configure(api_key=api_key)
                    response = chat_session.send_message(message)
                    return jsonify({'response': response.text})
            except Exception:
                pass
        print(f"Chat API Error: {str(e)}")
        error_msg = str(e)
        if '429' in error_msg or 'quota' in error_msg.lower():
            user_msg = "The AI service is currently receiving too many requests. Please wait a moment."
        else:
            user_msg = "An unexpected error occurred. Please try again."
        return jsonify({'error': user_msg}), 500

@app.route('/contact', methods=['GET'])
def contact():
    return render_template('contact.html')

@app.route('/api/export-pdf', methods=['POST'])
def export_pdf():
    """Generate a clean PDF server-side and return it as a download."""
    data = request.json
    summary = data.get('summary', '')
    profiles = data.get('profiles', '')
    
    if not summary:
        return jsonify({'error': 'No summary content to export'}), 400
    
    def strip_html(text):
        text = re.sub(r'<br\s*/?>', '\n', text)
        text = re.sub(r'</li>', '\n', text)
        text = re.sub(r'</p>', '\n\n', text)
        text = re.sub(r'<h[1-6][^>]*>', '\n\n', text)
        text = re.sub(r'</h[1-6]>', '\n', text)
        text = re.sub(r'<li[^>]*>', '  • ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = html_module.unescape(text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()
    
    clean_summary = strip_html(summary)
    clean_profiles = strip_html(profiles) if profiles else ''
    
    clean_summary = clean_summary.encode('latin-1', 'ignore').decode('latin-1')
    clean_profiles = clean_profiles.encode('latin-1', 'ignore').decode('latin-1')
    
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 20)
    pdf.cell(0, 12, 'ChatRecap - Analysis Report', new_x='LMARGIN', new_y='NEXT')
    
    pdf.set_font('Helvetica', '', 10)
    pdf.set_text_color(100, 116, 139)
    from datetime import datetime as dt
    pdf.cell(0, 8, f'Generated on {dt.now().strftime("%B %d, %Y at %I:%M %p")}', new_x='LMARGIN', new_y='NEXT')
    pdf.ln(6)
    
    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(8)
    
    pdf.set_text_color(15, 23, 42)
    pdf.set_font('Helvetica', '', 11)
    
    for line in clean_summary.split('\n'):
        line = line.strip()
        if not line:
            pdf.ln(4)
            continue
        if line.startswith('**') and line.endswith('**'):
            pdf.set_font('Helvetica', 'B', 12)
            pdf.multi_cell(0, 6, line.replace('**', ''))
            pdf.set_font('Helvetica', '', 11)
        elif line.startswith('  \u2022 '):
            pdf.multi_cell(0, 6, line)
        else:
            pdf.multi_cell(0, 6, line)
        pdf.ln(2)
    
    if clean_profiles:
        pdf.ln(8)
        pdf.set_draw_color(226, 232, 240)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(6)
        pdf.set_font('Helvetica', 'B', 14)
        pdf.cell(0, 10, 'Personality Profiles', new_x='LMARGIN', new_y='NEXT')
        pdf.ln(4)
        pdf.set_font('Helvetica', '', 11)
        for line in clean_profiles.split('\n'):
            line = line.strip()
            if not line:
                pdf.ln(4)
                continue
            pdf.multi_cell(0, 6, line)
            pdf.ln(2)
    
    pdf.ln(10)
    pdf.set_font('Helvetica', 'I', 9)
    pdf.set_text_color(148, 163, 184)
    pdf.cell(0, 8, 'Generated by ChatRecap', align='C')
    
    pdf_bytes = pdf.output()
    buffer = io.BytesIO(pdf_bytes)
    buffer.seek(0)
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='ChatRecap_Report.pdf'
    )

if __name__ == '__main__':
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5000)

"""
PrometheusAI - Chatbot with Web Search Capabilities and Document Upload
Flask Application with LM Studio, Web Scraping, and OCR Support
"""
import os
import json
import uuid
import sys
import socket
import re
import io
import base64
from datetime import datetime
from typing import List, Dict, Optional
from urllib.parse import urlparse, quote_plus
import time

import requests
from bs4 import BeautifulSoup
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from flask_cors import CORS
import logging

# PDF and Image processing
from PIL import Image
import pytesseract
import PyPDF2
import pdf2image

# Configure logging FIRST (before using logger)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configure Tesseract path for Windows (AFTER logger is defined)
if os.name == 'nt':  # Windows
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        logger.info(f"Tesseract found at: {tesseract_path}")
    else:
        # Try alternate common paths
        alternate_paths = [
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Tesseract-OCR\tesseract.exe'
        ]
        for path in alternate_paths:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                logger.info(f"Tesseract found at: {path}")
                break

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
CORS(app, supports_credentials=True)

# Persistent storage for chats (only for logged-in users)
CHAT_SESSIONS_FILE = 'chat_sessions.json'

# In-memory storage for anonymous sessions (not persisted)
anonymous_sessions = {}

# Upload folder
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def load_chat_sessions():
    """Load chat sessions from disk."""
    global chat_sessions
    if os.path.exists(CHAT_SESSIONS_FILE):
        try:
            with open(CHAT_SESSIONS_FILE, 'r', encoding='utf-8') as f:
                chat_sessions = json.load(f)
            logger.info(f"Loaded {len(chat_sessions)} chat sessions from disk")
        except Exception as e:
            logger.error(f"Failed to load chat sessions: {e}")
            chat_sessions = {}
    else:
        chat_sessions = {}

def save_chat_sessions():
    """Save chat sessions to disk (only for logged-in users)."""
    try:
        with open(CHAT_SESSIONS_FILE, 'w', encoding='utf-8') as f:
            json.dump(chat_sessions, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved {len(chat_sessions)} chat sessions to disk")
    except Exception as e:
        logger.error(f"Failed to save chat sessions: {e}")

# Load sessions on startup
load_chat_sessions()


class DocumentProcessor:
    """Process PDFs and images with OCR capabilities."""
    
    def __init__(self):
        """Initialize the document processor."""
        # Check if tesseract is available
        try:
            pytesseract.get_tesseract_version()
            self.ocr_available = True
            logger.info("Tesseract OCR is available")
        except Exception as e:
            self.ocr_available = False
            logger.warning(f"Tesseract OCR not available: {e}")
    
    def extract_text_from_pdf(self, file_path: str) -> Dict[str, any]:
        """Extract text from PDF, fallback to OCR if needed."""
        try:
            text = ""
            pages = 0
            
            # Try extracting text directly
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    page_text = page.extract_text()
                    if page_text:
                        text += f"\n--- Page {page_num + 1} ---\n{page_text}"
            
            # If no text extracted and OCR is available, try OCR
            if not text.strip() and self.ocr_available:
                logger.info("No text found in PDF, attempting OCR...")
                text = self.ocr_pdf(file_path)
                
            return {
                'success': True,
                'text': text.strip(),
                'pages': pages,
                'method': 'direct' if text.strip() and not self.ocr_available else 'ocr'
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def ocr_pdf(self, file_path: str, max_pages: int = 10) -> str:
        """Perform OCR on PDF pages."""
        try:
            # For Windows, you may need to specify poppler path
            # Download poppler from: https://github.com/oschwartz10612/poppler-windows/releases/
            # Extract and set path, e.g.: poppler_path = r'C:\path\to\poppler\bin'
            
            try:
                # Try without poppler path first (if it's in PATH)
                images = pdf2image.convert_from_path(file_path, dpi=200)
            except Exception as e:
                logger.warning(f"pdf2image failed without poppler path: {e}")
                # Try common Windows poppler locations
                poppler_paths = [
                    r'C:\Program Files\poppler\Library\bin',
                    r'C:\poppler\Library\bin',
                    r'C:\Program Files (x86)\poppler\bin'
                ]
                
                images = None
                for poppler_path in poppler_paths:
                    if os.path.exists(poppler_path):
                        try:
                            images = pdf2image.convert_from_path(file_path, dpi=200, poppler_path=poppler_path)
                            logger.info(f"Using poppler from: {poppler_path}")
                            break
                        except:
                            continue
                
                if images is None:
                    return "[OCR Error: Poppler not found. Please install poppler-utils for PDF OCR. See: https://github.com/oschwartz10612/poppler-windows/releases/]"
            
            text = ""
            for i, image in enumerate(images[:max_pages]):
                logger.info(f"OCR processing page {i + 1}...")
                page_text = pytesseract.image_to_string(image)
                text += f"\n--- Page {i + 1} (OCR) ---\n{page_text}"
            
            if len(images) > max_pages:
                text += f"\n\n[Note: Only processed first {max_pages} pages of {len(images)} total pages]"
            
            return text
            
        except Exception as e:
            logger.error(f"Error performing OCR on PDF: {e}")
            return f"[OCR Error: {str(e)}]"
    
    def extract_text_from_image(self, file_path: str) -> Dict[str, any]:
        """Extract text from image using OCR."""
        try:
            if not self.ocr_available:
                return {
                    'success': False,
                    'error': 'OCR is not available. Please install Tesseract.'
                }
            
            # Open and process image
            image = Image.open(file_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Perform OCR
            text = pytesseract.image_to_string(image)
            
            return {
                'success': True,
                'text': text.strip(),
                'method': 'ocr'
            }
            
        except Exception as e:
            logger.error(f"Error extracting text from image: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def process_file(self, file_path: str, file_type: str) -> Dict[str, any]:
        """Process file based on type."""
        if file_type == 'pdf':
            return self.extract_text_from_pdf(file_path)
        elif file_type in ['image', 'jpg', 'jpeg', 'png', 'gif', 'bmp']:
            return self.extract_text_from_image(file_path)
        else:
            return {
                'success': False,
                'error': f'Unsupported file type: {file_type}'
            }


class WebSearcher:
    """Web search and scraping functionality with multiple fallback options."""
    
    def __init__(self):
        """Initialize the web searcher."""
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)

    def search_brave(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        try:
            search_url = f"https://search.brave.com/search?q={quote_plus(query)}"
            response = self.session.get(search_url, timeout=10)
            if response.status_code != 200:
                logger.error(f"Brave search failed with status {response.status_code}")
                return []
            
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.find_all('div', class_='snippet fdb')[:num_results]:
                try:
                    title_elem = result.find('p', class_='snippet-title')
                    url_elem = result.find('cite', class_='snippet-url')
                    snippet_elem = result.find('p', class_='snippet-description')
                    
                    if title_elem and url_elem:
                        title = title_elem.get_text(strip=True)
                        url = result.find('a')['href'] if result.find('a') else ''
                        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ''
                        
                        if url and title and not url.startswith('javascript:'):
                            results.append({'title': title, 'url': url, 'snippet': snippet})
                except Exception as e:
                    logger.error(f"Error parsing Brave result: {e}")
                    continue
            
            logger.info(f"Found {len(results)} results from Brave for: {query}")
            return results
        except Exception as e:
            logger.error(f"Error searching Brave: {e}")
            return []

    def search_html_fallback(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        search_engines = [
            {'url': f"https://www.bing.com/search?q={quote_plus(query)}", 'type': 'bing'},
            {'url': f"https://www.google.com/search?q={quote_plus(query)}", 'type': 'google'},
        ]
        
        for engine in search_engines:
            try:
                response = self.session.get(engine['url'], timeout=10)
                if response.status_code != 200:
                    continue
                
                soup = BeautifulSoup(response.text, 'html.parser')
                results = []
                
                if engine['type'] == 'bing':
                    for container in soup.find_all('li', class_='b_algo')[:num_results]:
                        title_elem = container.find('h2')
                        link_elem = title_elem.find('a') if title_elem else None
                        snippet_elem = container.find('p')
                        if link_elem:
                            results.append({
                                'title': link_elem.get_text(strip=True),
                                'url': link_elem.get('href', ''),
                                'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                            })
                
                elif engine['type'] == 'google':
                    for container in soup.find_all('div', class_='g')[:num_results]:
                        title_elem = container.find('h3')
                        link_elem = container.find('a')
                        snippet_elem = container.find('div', class_='VwiC3b')
                        if title_elem and link_elem:
                            results.append({
                                'title': title_elem.get_text(strip=True),
                                'url': link_elem.get('href', ''),
                                'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                            })
                
                if results:
                    logger.info(f"Found {len(results)} results from {engine['type']} fallback search")
                    return results
            except Exception as e:
                logger.error(f"Fallback search attempt failed for {engine['type']}: {e}")
                continue
        
        return []
        
    def search_google(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """Search using multiple methods with fallbacks."""
        results = self.search_brave(query, num_results)
        
        if not results:
            logger.info("Brave search failed, trying fallback methods...")
            results = self.search_html_fallback(query, num_results)
        
        if not results and any(keyword in query.lower() for keyword in ['time', 'date', 'current', 'today', 'now']):
            logger.info("Creating synthetic time/date result")
            results = [{
                'title': 'Current Date and Time Information',
                'url': 'https://www.timeanddate.com/',
                'snippet': 'Current time and date information. Note: For real-time data, please visit timeanddate.com directly.'
            }]
        
        return results
    
    def scrape_url(self, url: str, max_chars: int = 5000) -> Optional[str]:
        """Scrape content from a URL."""
        try:
            logger.info(f"Scraping URL: {url}")
            response = self.session.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch URL: {response.status_code}")
                return None
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            if len(text) > max_chars:
                text = text[:max_chars] + "..."
            
            logger.info(f"Scraped {len(text)} characters from {url}")
            return text
            
        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
            return None
    
    def search_and_scrape(self, query: str, num_urls: int = 3) -> Dict[str, any]:
        """Search and scrape top results."""
        search_results = self.search_google(query, num_results=num_urls)
        
        if not search_results:
            return {
                'success': False,
                'error': 'No search results found'
            }
        
        scraped_data = []
        for result in search_results[:num_urls]:
            content = self.scrape_url(result['url'])
            if content:
                scraped_data.append({
                    'title': result['title'],
                    'url': result['url'],
                    'snippet': result['snippet'],
                    'content': content
                })
            else:
                scraped_data.append({
                    'title': result['title'],
                    'url': result['url'],
                    'snippet': result['snippet'],
                    'content': result['snippet']
                })
        
        return {
            'success': True,
            'query': query,
            'results': scraped_data
        }


class SimpleChatbot:
    """Simple chatbot using LM Studio local API with web search and document processing capabilities."""
    
    def __init__(
        self,
        lm_studio_url: str = "http://localhost:1200/v1/chat/completions",
        model_name: str = "ibm/granite-4-h-tiny"
    ):
        """Initialize the chatbot."""
        self.lm_studio_url = lm_studio_url
        self.model_name = model_name
        self.web_searcher = WebSearcher()
        self.doc_processor = DocumentProcessor()
        logger.info("Chatbot initialized with web search and document processing capabilities!")
    
    def clean_text(self, text: str) -> str:
        """Clean text from encoding issues and unwanted characters."""
        if not text:
            return ""
        
        cleaned = text.replace('\ufffd', '')
        cleaned = ''.join(char for char in cleaned if ord(char) < 0x10000)
        
        return cleaned
    
    def should_search_web(self, query: str) -> bool:
        """Determine if the query requires web search."""
        search_indicators = [
            'latest', 'current', 'recent', 'today', 'news', 'courses at',
            'programs at', 'what are the', 'list', 'find', 'search',
            'website', 'url', 'information about', 'details about',
            'time', 'date', 'now', 'right now', 'currently',
            'what is the date', 'what is the time', 'what time is it'
        ]
        
        query_lower = query.lower()
        
        time_date_keywords = ['time', 'date', 'today', 'now', 'right now', 'currently', 'what time']
        if any(keyword in query_lower for keyword in time_date_keywords):
            return True
        
        if any(term in query_lower for term in ['university', 'college', 'school', 'courses', 'programs']):
            return True
        
        return any(indicator in query_lower for indicator in search_indicators)
    
    def extract_search_query(self, user_query: str) -> str:
        """Extract a good search query from user's question."""
        query_lower = user_query.lower()
        
        if 'time' in query_lower and 'india' in query_lower:
            return "current time in India IST"
        elif 'date' in query_lower and 'india' in query_lower:
            return "current date in India"
        elif 'time' in query_lower or 'date' in query_lower:
            return "current time and date"
        
        search_query = user_query
        question_words = ['what are', 'tell me', 'show me', 'can you', 'please', 'find', 'what is', 'what\'s']
        
        for word in question_words:
            search_query = search_query.lower().replace(word, '')
        
        return search_query.strip()
    
    def query_lm_studio(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = -1
    ) -> str:
        """Query LM Studio API."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False
        }
        
        try:
            logger.info(f"Sending request to LM Studio (model: {self.model_name})")
            response = requests.post(
                self.lm_studio_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60
            )

            if not response.ok:
                body_text = None
                try:
                    body_json = response.json()
                    body_text = body_json.get('error', {}).get('message') or str(body_json)
                except Exception:
                    body_text = response.text

                logger.error(f"LM Studio returned status {response.status_code}: {body_text}")
                
                if 'model_not_found' in str(body_text).lower() and 'your models:' in str(body_text).lower():
                    try:
                        marker = 'Your models:'
                        parts = str(body_text).split(marker, 1)
                        if len(parts) > 1:
                            candidates = [line.strip() for line in parts[1].splitlines() if line.strip()]
                            if candidates:
                                chosen = candidates[0]
                                logger.info(f"Retrying with fallback model '{chosen}'")
                                self.model_name = chosen
                                retry_payload = {**payload, 'model': self.model_name}
                                retry_resp = requests.post(
                                    self.lm_studio_url,
                                    headers={"Content-Type": "application/json"},
                                    json=retry_payload,
                                    timeout=60
                                )
                                if retry_resp.ok:
                                    result = retry_resp.json()['choices'][0]['message']['content']
                                    return self.clean_text(result)
                    except Exception as e:
                        logger.error(f"Error during fallback: {e}")
                
                return "Sorry, the language model returned an error. Please check that LM Studio is running and a model is loaded."

            result = response.json()
            content = result['choices'][0]['message']['content']
            return self.clean_text(content)

        except requests.exceptions.RequestException as e:
            logger.error(f"Error querying LM Studio: {e}")
            return "Sorry, I couldn't connect to the language model. Please ensure LM Studio is running at http://localhost:1200"
    
    def query_lm_studio_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = -1,
        timeout: int = 120
    ):
        """Query LM Studio API in streaming mode."""
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        try:
            logger.info(f"Sending streaming request to LM Studio (model: {self.model_name})")
            resp = requests.post(
                self.lm_studio_url,
                headers={"Content-Type": "application/json"},
                json=payload,
                stream=True,
                timeout=timeout
            )

            if not resp.ok:
                try:
                    body = resp.json()
                except Exception:
                    body = resp.text
                yield f"[ERROR] {body}"
                return

            for raw_line in resp.iter_lines(decode_unicode=True):
                if raw_line is None:
                    continue
                line = raw_line.strip()
                if not line:
                    continue

                if line.startswith('data:'):
                    line = line[len('data:'):].strip()

                if line == '[DONE]':
                    break

                try:
                    obj = json.loads(line)
                    choices = obj.get('choices') if isinstance(obj, dict) else None
                    if choices:
                        ch = choices[0]
                        delta = ch.get('delta', {})
                        if isinstance(delta, dict) and 'content' in delta:
                            content = delta.get('content')
                            if content:
                                clean_content = self.clean_text(content)
                                if clean_content:
                                    yield clean_content
                        elif ch.get('message'):
                            msg_content = ch['message'].get('content')
                            if msg_content:
                                clean_content = self.clean_text(msg_content)
                                if clean_content:
                                    yield clean_content
                except Exception as e:
                    logger.error(f"Error parsing stream chunk: {e}")
                    continue

        except requests.exceptions.RequestException as e:
            yield f"[ERROR] Error querying LM Studio: {e}"
            return
    
    def chat(
        self,
        user_query: str,
        conversation_history: List[Dict[str, str]] = None,
        temperature: float = 0.7,
        document_context: str = None
    ) -> str:
        """Process a user query with optional web search and document context."""
        
        web_context = ""
        if self.should_search_web(user_query):
            logger.info("Web search triggered for query")
            search_query = self.extract_search_query(user_query)
            
            web_data = self.web_searcher.search_and_scrape(search_query, num_urls=2)
            
            if web_data['success'] and web_data['results']:
                web_context = "\n\nWeb Search Results:\n"
                for idx, result in enumerate(web_data['results'], 1):
                    web_context += f"\n[Source {idx}] {result['title']}\n"
                    web_context += f"URL: {result['url']}\n"
                    web_context += f"Content: {result['content'][:1500]}...\n"
                
                logger.info(f"Added web context from {len(web_data['results'])} sources")
        
        system_prompt = (
            "You are PrometheusAI, a helpful and friendly AI assistant built by SamCodeMan's LLC. "
            "You provide accurate, helpful, and conversational responses. "
            
            "CRITICAL INSTRUCTION: If the user asks about current time, date, or 'right now' information, "
            "you MUST use the web search results provided. DO NOT use your internal knowledge for time-sensitive queries. "
            "Your training data is outdated for current information. Always rely on web search results when provided. "
            
            "When web search results are provided, use them to answer the user's question accurately. "
            "Always cite your sources by mentioning the website or URL when using web information. "
            
            "When document content is provided (from uploaded PDFs or images), use that information to answer questions accurately. "
            "Reference the document when providing answers based on its content. "
            
            "If web search results or document content don't contain the exact answer, acknowledge this and provide the best answer you can. "
            "Be concise but informative, and maintain a friendly tone. "
            "Do not use emojis or special characters in your responses."
        )
        
        messages = [{"role": "system", "content": system_prompt}]
        
        if conversation_history:
            messages.extend(conversation_history[-10:])
        
        user_message = user_query
        
        if document_context:
            user_message = f"[Document Content]\n{document_context}\n\n[User Question]\n{user_query}"
        
        if web_context:
            user_message += web_context
            user_message += "\n\nIMPORTANT: Use ONLY the information from the web search results above to answer. Do not use outdated information."
        
        messages.append({"role": "user", "content": user_message})
        
        logger.info("Generating response...")
        response = self.query_lm_studio(messages, temperature=temperature)
        
        return response


# Global instances
CHATBOT = None


def get_chatbot() -> SimpleChatbot:
    """Get or initialize the chatbot instance."""
    global CHATBOT
    
    if CHATBOT is not None:
        return CHATBOT
    
    lm_studio_url = os.environ.get('LM_STUDIO_URL', 'http://localhost:1200/v1/chat/completions')
    model_name = os.environ.get('MODEL_NAME', 'ibm/granite-4-h-tiny')
    
    logger.info(f"Configuration:")
    logger.info(f"   - LM Studio URL: {lm_studio_url}")
    logger.info(f"   - Model: {model_name}")
    
    CHATBOT = SimpleChatbot(
        lm_studio_url=lm_studio_url,
        model_name=model_name
    )
    
    return CHATBOT


# ============================================================================
# Flask Routes
# ============================================================================

@app.route('/')
def index():
    """Serve the main chat interface."""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Handle file uploads (PDF and images)."""
    try:
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': 'No file provided'
            }), 400
        
        file = request.files['file']
        
        if file.filename == '':
            return jsonify({
                'success': False,
                'error': 'No file selected'
            }), 400
        
        # Get file extension
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        # Validate file type
        allowed_extensions = ['pdf', 'jpg', 'jpeg', 'png', 'gif', 'bmp']
        if file_ext not in allowed_extensions:
            return jsonify({
                'success': False,
                'error': f'Unsupported file type. Allowed: {", ".join(allowed_extensions)}'
            }), 400
        
        # Save file temporarily
        file_id = str(uuid.uuid4())
        filename = f"{file_id}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)
        
        logger.info(f"File uploaded: {filename}")
        
        # Process file
        bot = get_chatbot()
        file_type = 'pdf' if file_ext == 'pdf' else 'image'
        result = bot.doc_processor.process_file(file_path, file_type)
        
        # Clean up file
        try:
            os.remove(file_path)
        except:
            pass
        
        if result['success']:
            return jsonify({
                'success': True,
                'file_id': file_id,
                'file_name': file.filename,
                'file_type': file_type,
                'text': result['text'],
                'method': result.get('method', 'unknown'),
                'pages': result.get('pages', None)
            })
        else:
            return jsonify({
                'success': False,
                'error': result.get('error', 'Failed to process file')
            }), 500
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chats', methods=['GET'])
def get_chats():
    """Get list of all chat sessions for a logged-in user."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 401
        
        user_chats = {k: v for k, v in chat_sessions.items() if v.get('user_id') == user_id}
        chats = list(user_chats.values())
        chats.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        return jsonify({
            'success': True,
            'chats': chats
        })
    except Exception as e:
        logger.error(f"Error getting chats: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/new-chat', methods=['POST'])
def new_chat():
    """Create a new chat session (only for logged-in users)."""
    try:
        data = request.json
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'Authentication required to save chats'
            }), 401
        
        chat_id = str(uuid.uuid4())
        chat_sessions[chat_id] = {
            'id': chat_id,
            'user_id': user_id,
            'title': 'New chat',
            'messages': [],
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }
        logger.info(f"Created new chat session: {chat_id} for user: {user_id}")
        save_chat_sessions()
        return jsonify({
            'success': True,
            'chat_id': chat_id
        })
    except Exception as e:
        logger.error(f"Error creating new chat: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chats/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Get a specific chat's messages."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 401
        
        if chat_id not in chat_sessions:
            return jsonify({
                'success': False,
                'error': 'Chat not found'
            }), 404
        
        if chat_sessions[chat_id].get('user_id') != user_id:
            return jsonify({
                'success': False,
                'error': 'Access denied'
            }), 403
        
        return jsonify({
            'success': True,
            'chat': chat_sessions[chat_id]
        })
    except Exception as e:
        logger.error(f"Error getting chat {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chats/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Delete a chat session."""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({
                'success': False,
                'error': 'User ID required'
            }), 401
        
        if chat_id in chat_sessions:
            if chat_sessions[chat_id].get('user_id') != user_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
            
            del chat_sessions[chat_id]
            save_chat_sessions()
            logger.info(f"Deleted chat session: {chat_id}")
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error deleting chat {chat_id}: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/chat', methods=['POST'])
def chat():
    """Process a chat message and return AI response."""
    try:
        data = request.json
        chat_id = data.get('chat_id')
        message = data.get('message', '').strip()
        user_id = data.get('user_id')
        document_context = data.get('document_context')
        
        if not message:
            return jsonify({
                'success': False,
                'error': 'Message cannot be empty'
            }), 400
        
        is_logged_in = user_id is not None and user_id != ''
        
        if is_logged_in:
            if not chat_id or chat_id not in chat_sessions:
                chat_id = str(uuid.uuid4())
                chat_sessions[chat_id] = {
                    'id': chat_id,
                    'user_id': user_id,
                    'title': message[:50] + ('...' if len(message) > 50 else ''),
                    'messages': [],
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                logger.info(f"Created new chat session: {chat_id} for user: {user_id}")
            
            if chat_sessions[chat_id].get('user_id') != user_id:
                return jsonify({
                    'success': False,
                    'error': 'Access denied'
                }), 403
            
            session = chat_sessions[chat_id]
        else:
            if not chat_id or chat_id not in anonymous_sessions:
                chat_id = str(uuid.uuid4())
                anonymous_sessions[chat_id] = {
                    'id': chat_id,
                    'messages': [],
                    'created_at': datetime.now().isoformat()
                }
                logger.info(f"Created anonymous chat session: {chat_id}")
            
            session = anonymous_sessions[chat_id]
        
        show_login_reminder = not is_logged_in and len(session['messages']) == 0
        
        user_msg = {
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        }
        session['messages'].append(user_msg)
        
        bot = get_chatbot()
        
        conversation_history = []
        for msg in session['messages'][:-1]:
            conversation_history.append({
                'role': msg['role'],
                'content': msg['content']
            })
        
        ai_response = bot.chat(
            message,
            conversation_history=conversation_history if conversation_history else None,
            temperature=0.7,
            document_context=document_context
        )
        
        if show_login_reminder:
            login_reminder = (
                "Note: You are chatting anonymously. Your conversation will not be saved. "
                "If you want to save your chat history, please login with Google.\n\n"
            )
            ai_response = login_reminder + ai_response
        
        ai_msg = {
            'role': 'assistant',
            'content': ai_response,
            'timestamp': datetime.now().isoformat()
        }
        session['messages'].append(ai_msg)
        
        if is_logged_in:
            session['updated_at'] = datetime.now().isoformat()
            
            if len(session['messages']) == 2:
                session['title'] = message[:50] + ('...' if len(message) > 50 else '')
            
            save_chat_sessions()
        
        logger.info(f"Generated response for chat {chat_id} ({'logged-in' if is_logged_in else 'anonymous'})")
        
        return jsonify({
            'success': True,
            'chat_id': chat_id,
            'response': ai_response,
            'is_anonymous': not is_logged_in
        })
        
    except Exception as e:
        logger.error(f"Error processing chat: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500


@app.route('/api/chat/stream', methods=['POST'])
def chat_stream():
    """Streaming chat endpoint with web search and document context support."""
    try:
        data = request.json
        chat_id = data.get('chat_id')
        message = data.get('message', '').strip()
        user_id = data.get('user_id')
        document_context = data.get('document_context')

        if not message:
            return jsonify({'success': False, 'error': 'Message cannot be empty'}), 400

        is_logged_in = user_id is not None and user_id != ''
        
        if is_logged_in:
            if not chat_id or chat_id not in chat_sessions:
                chat_id = str(uuid.uuid4())
                chat_sessions[chat_id] = {
                    'id': chat_id,
                    'user_id': user_id,
                    'title': message[:50] + ('...' if len(message) > 50 else ''),
                    'messages': [],
                    'created_at': datetime.now().isoformat(),
                    'updated_at': datetime.now().isoformat()
                }
                logger.info(f"Created new chat session: {chat_id} for user: {user_id}")
            
            if chat_sessions[chat_id].get('user_id') != user_id:
                return jsonify({'success': False, 'error': 'Access denied'}), 403
            
            session = chat_sessions[chat_id]
        else:
            if not chat_id or chat_id not in anonymous_sessions:
                chat_id = str(uuid.uuid4())
                anonymous_sessions[chat_id] = {
                    'id': chat_id,
                    'messages': [],
                    'created_at': datetime.now().isoformat()
                }
                logger.info(f"Created anonymous chat session: {chat_id}")
            
            session = anonymous_sessions[chat_id]
        
        show_login_reminder = not is_logged_in and len(session['messages']) == 0

        user_msg = {
            'role': 'user',
            'content': message,
            'timestamp': datetime.now().isoformat()
        }
        session['messages'].append(user_msg)

        bot = get_chatbot()

        conversation_history = []
        for msg in session['messages'][:-1]:
            conversation_history.append({'role': msg['role'], 'content': msg['content']})

        web_context = ""
        web_search_performed = False
        if bot.should_search_web(message):
            logger.info("Web search triggered for streaming query")
            search_query = bot.extract_search_query(message)
            
            web_data = bot.web_searcher.search_and_scrape(search_query, num_urls=2)
            
            if web_data['success'] and web_data['results']:
                web_search_performed = True
                web_context = "\n\nWeb Search Results:\n"
                for idx, result in enumerate(web_data['results'], 1):
                    web_context += f"\n[Source {idx}] {result['title']}\n"
                    web_context += f"URL: {result['url']}\n"
                    web_context += f"Content: {result['content'][:1500]}...\n"
                
                logger.info(f"Added web context from {len(web_data['results'])} sources")

        system_prompt = (
            "You are PrometheusAI, a helpful and friendly AI assistant built by SamCodeMan LLC. "
            "You provide accurate, helpful, and conversational responses. "
            
            "CRITICAL INSTRUCTION: If the user asks about current time, date, or 'right now' information, "
            "you MUST use the web search results provided. DO NOT use your internal knowledge for time-sensitive queries. "
            "Your training data is outdated for current information. Always rely on web search results when provided. "
            
            "When web search results are provided, use them to answer the user's question accurately. "
            "Always cite your sources by mentioning the website or URL when using web information. "
            
            "When document content is provided (from uploaded PDFs or images), use that information to answer questions accurately. "
            "Reference the document when providing answers based on its content. "
            
            "If web search results or document content don't contain the exact answer, acknowledge this and suggest the user visit the source directly. "
            "Be concise but informative, and maintain a friendly tone. "
            "Do not use emojis or special characters in your responses."
        )

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history[-10:])
        
        user_message = message
        
        if document_context:
            user_message = f"[Document Content]\n{document_context}\n\n[User Question]\n{message}"
        
        if web_context:
            user_message += web_context
            user_message += "\n\nIMPORTANT: Use ONLY the information from the web search results above to answer. Do not use outdated information."
        
        messages.append({'role': 'user', 'content': user_message})

        def generate():
            final_text = ''
            try:
                if show_login_reminder:
                    reminder = (
                        "Note: You are chatting anonymously. Your conversation will not be saved. "
                        "If you want to save your chat history, please login with Google.\n\n"
                    )
                    payload = {'type': 'delta', 'delta': reminder}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    final_text += reminder
                
                if web_search_performed:
                    search_notice = "[Searching the web...]\n\n"
                    payload = {'type': 'delta', 'delta': search_notice}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                    final_text += search_notice
                
                for chunk in bot.query_lm_studio_stream(messages, temperature=0.7):
                    final_text += chunk
                    payload = {'type': 'delta', 'delta': chunk}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

                ai_msg = {
                    'role': 'assistant',
                    'content': final_text,
                    'timestamp': datetime.now().isoformat()
                }
                session['messages'].append(ai_msg)
                
                if is_logged_in:
                    session['updated_at'] = datetime.now().isoformat()
                    
                    if len(session['messages']) == 2:
                        session['title'] = message[:50] + ('...' if len(message) > 50 else '')
                    
                    save_chat_sessions()
                
                logger.info(f"Streaming completed for chat {chat_id} ({'logged-in' if is_logged_in else 'anonymous'})")

                done_payload = {
                    'type': 'done',
                    'chat_id': chat_id,
                    'final': final_text,
                    'is_anonymous': not is_logged_in
                }
                yield f"data: {json.dumps(done_payload, ensure_ascii=False)}\n\n"

            except Exception as e:
                logger.error(f"Error in streaming generation: {e}", exc_info=True)
                err_payload = {'type': 'error', 'error': str(e)}
                yield f"data: {json.dumps(err_payload, ensure_ascii=False)}\n\n"

        return Response(
            stream_with_context(generate()), 
            mimetype='text/event-stream; charset=utf-8',
            headers={
                'Cache-Control': 'no-cache',
                'X-Accel-Buffering': 'no'
            }
        )

    except Exception as e:
        logger.error(f"Error in streaming chat: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/web-search', methods=['POST'])
def web_search():
    """Direct web search endpoint."""
    try:
        data = request.json
        query = data.get('query', '').strip()
        num_results = data.get('num_results', 3)
        
        if not query:
            return jsonify({
                'success': False,
                'error': 'Query cannot be empty'
            }), 400
        
        bot = get_chatbot()
        results = bot.web_searcher.search_and_scrape(query, num_urls=num_results)
        
        return jsonify(results)
        
    except Exception as e:
        logger.error(f"Error in web search: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/health')
def health():
    """Health check endpoint."""
    try:
        bot = get_chatbot()
        
        try:
            test_response = bot.query_lm_studio(
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": "Reply with just 'OK'"}
                ],
                temperature=0.0
            )
            lm_status = 'ok' if 'ok' in test_response.lower() else 'degraded'
        except Exception as e:
            lm_status = f'error: {str(e)}'
        
        return jsonify({
            'status': 'ok' if lm_status == 'ok' else 'degraded',
            'service': 'PrometheusAI - Chatbot with Web Search & Document Processing',
            'lm_studio': lm_status,
            'saved_chats': len(chat_sessions),
            'anonymous_chats': len(anonymous_sessions),
            'web_search': 'enabled',
            'ocr': 'enabled' if bot.doc_processor.ocr_available else 'disabled',
            'config': {
                'model': bot.model_name
            }
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'error': str(e)
        }), 500


# ============================================================================
# Application Startup
# ============================================================================

def check_port_availability(port):
    """Check if port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(('localhost', port)) == 0

if __name__ == '__main__':
    print("\n" + "="*70)
    print("PrometheusAI - Chatbot with Web Search & Document Processing")
    print("="*70)
    print()
    
    try:
        bot = get_chatbot()
        print()
        print("="*70)
        print("PrometheusAI is ready to serve requests!")
        print("="*70)
        print()
        print("Features:")
        print("  ✓ LM Studio Integration")
        print("  ✓ Multi-Engine Web Search (Brave/Bing fallback)")
        print("  ✓ PDF & Image Upload with OCR")
        print("  ✓ Anonymous & Authenticated Chat")
        print("  ✓ Persistent Chat History")
        print()
        print("Access the application at: http://localhost:5000")
        print("Health check at: http://localhost:5000/health")
        print()
        print("Make sure LM Studio is running at http://localhost:1200")
        print("    with a model loaded before sending chat requests!")
        print()
        if bot.doc_processor.ocr_available:
            print("✓ Tesseract OCR is available for document processing")
        else:
            print("⚠ Tesseract OCR not available - OCR features disabled")
            print("  Install Tesseract: https://github.com/tesseract-ocr/tesseract")
        print()
    except Exception as e:
        print(f"Warning: Could not initialize chatbot at startup")
        print(f"   Error: {e}")
        print("   The chatbot will be initialized on first request.")
        print()
    
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    
    if check_port_availability(port):
        print(f"Port {port} is already in use!")
        print(f"   Trying port {port + 1} instead...")
        port += 1
    
    if debug and 'debugpy' in sys.modules:
        print("VS Code debugger detected - disabling Flask reloader")
        use_reloader = False
    else:
        use_reloader = debug
    
    try:
        app.run(
            host='0.0.0.0',
            port=port,
            debug=debug,
            use_reloader=use_reloader,
            threaded=True
        )
    except SystemExit as e:
        if e.code == 3:
            print(f"Flask reloader exited. Server may be running on port {port}")
            print("   If not, try running with DEBUG=False or set a different PORT")
        else:
            raise
    except OSError as e:
        if e.errno == 10048:
            print(f"Port {port} is already in use by another process!")
            print("   Kill the process or set a different PORT environment variable.")
            sys.exit(1)
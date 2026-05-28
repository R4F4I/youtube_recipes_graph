import os
import re
import json
import sqlite3
import logging
from todoist_api_python.api import TodoistAPI
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
from huggingface_hub import InferenceClient

# ==========================================
# 1. LOGGING CONFIGURATION (DEBUG MODE)
# ==========================================
# This configures logging to print highly detailed logs to your console.
# Format: YYYY-MM-DD HH:MM:SS - LEVEL - [FunctionName] - Message
logging.basicConfig(
    level=logging.DEBUG,  # Set to logging.INFO later if you want less noise
    format='%(asctime)s - %(levelname)s - [%(funcName)s] - %(message)s',
    handlers=[
        logging.StreamHandler(),                      # Print to console
        logging.FileHandler("pantry_pipeline.log", encoding="utf-8") # Save to a file
    ]
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. WINDOWS ENVIRONMENT & CONFIGURATION
# ==========================================
logger.debug("Retrieving Windows environment variables...")
TODOIST_API_KEY = os.environ.get("TODOIST_API")
HF_TOKEN = os.environ.get("HF_TOKEN")

# Raw string for Windows paths
OBSIDIAN_VAULT_PATH = r"D:\rafay\projects\youtube_recipes_graph\recipies_vault" 
PROJECT_NAME = "yt links"

if not TODOIST_API_KEY:
    logger.critical("Windows Environment Variable 'TODOIST_API_KEY' is missing!")
    raise ValueError("Missing TODOIST_API_KEY")

if not HF_TOKEN:
    logger.critical("Windows Environment Variable 'HF_TOKEN' is missing!")
    raise ValueError("Missing HF_TOKEN")

logger.info("Environment variables verified successfully.")

# Initialize Clients
logger.debug("Initializing Todoist and Hugging Face API clients...")
todoist = TodoistAPI(TODOIST_API_KEY)
hf_client = InferenceClient("Qwen/Qwen2.5-7B-Instruct", token=HF_TOKEN)

# ==========================================
# 3. LOCAL DATABASE SETUP (SQLite)
# ==========================================
def init_db():
    logger.debug("Opening connection to local SQLite database 'pantry.db'...")
    conn = sqlite3.connect("pantry.db")
    cursor = conn.cursor()
    
    logger.debug("Ensuring 'processed_videos' table exists...")
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS processed_videos (
            video_id TEXT PRIMARY KEY,
            status TEXT
        )
    ''')
    conn.commit()
    logger.info("SQLite database initialized successfully.")
    return conn

# ==========================================
# 4. CORE PROCESSING FUNCTIONS
# ==========================================
def extract_video_id(text):
    logger.debug(f"Attempting to extract YouTube ID from string fragment: '{text[:50]}...'")
    match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", text)
    if match:
        v_id = match.group(1)
        logger.debug(f"Successfully extracted Video ID: {v_id}")
        return v_id
    logger.debug("No 11-character YouTube video ID found in this text block.")
    return None

def get_transcript(video_id):
    logger.info(f"Fetching transcript for YouTube video: {video_id}")
    try:
        # FIX: Instantiate the API object first to support the latest library versions
        logger.debug("Instantiating YouTubeTranscriptApi client instance...")
        ytt_api = YouTubeTranscriptApi()
        
        # FIX: Use the instance method .fetch() instead of the removed static method
        logger.debug("Calling .fetch() on API instance to extract captions...")
        transcript_raw = ytt_api.fetch(video_id)
        logger.debug(f"Raw transcript fetched. Total timestamp blocks received: {len(transcript_raw)}")
        
        # Format transcript blocks into text
        logger.debug("Formatting raw timestamps into text blocks using TextFormatter...")
        formatter = TextFormatter()
        text_block = formatter.format_transcript(transcript_raw)
        
        # Clean text into free-flowing prose
        logger.debug("Cleaning text: Stripping line breaks and normalizing whitespace...")
        free_flowing_text = text_block.replace("\n", " ").strip()
        free_flowing_text = re.sub(r'\s+', ' ', free_flowing_text)
        
        logger.debug(f"Transcript processing complete. Total character count: {len(free_flowing_text)}")
        return free_flowing_text
        
    except Exception as e:
        logger.error(f"Failed to fetch/clean transcript for video {video_id}. Error: {str(e)}", exc_info=True)
        return None

def process_with_llm(transcript):
    logger.info("Preparing payload for Hugging Face Serverless Inference API...")
    system_prompt = """You are a culinary data extractor. Read the video transcript and extract the recipe into the exact JSON format requested. Do not include any text outside the JSON block.
    
    EXPECTED JSON SCHEMA:
    {
      "recipe_name": "Name of the dish",
      "time_minutes": 30,
      "components": [
        {
          "name": "Component Name (e.g. Protein, Sauce, Garnish)",
          "ingredients": ["Clean ingredient name 1", "Clean ingredient name 2"]
        }
      ]
    }"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Extract the recipe from this transcript:\n\n{transcript}"}
    ]
    
    logger.debug(f"Sending request to model 'Qwen/Qwen2.5-7B-Instruct'. Payload sizes - System Prompt: {len(system_prompt)} chars, Transcript: {len(transcript)} chars.")
    response = hf_client.chat_completion(
        messages=messages,
        max_tokens=1000,
        temperature=0.1
    )
    
    raw_output = response.choices[0].message.content
    logger.debug(f"Raw response block received from Hugging Face model:\n{raw_output}")
    
    logger.debug("Stripping potential markdown code fence wrappers from JSON output...")
    clean_json = re.sub(r'```json|```', '', raw_output).strip()
    
    logger.debug("Parsing cleaned string into a native Python dictionary...")
    recipe_dict = json.loads(clean_json)
    logger.info(f"Successfully generated structured data object for recipe: '{recipe_dict.get('recipe_name')}'")
    return recipe_dict

def save_to_obsidian(video_id, recipe_data):
    title = recipe_data.get("recipe_name", f"Recipe_{video_id}")
    logger.debug(f"Sanitizing recipe title '{title}' for Windows filesystem compatibility...")
    title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    
    filename = f"{title}.md"
    filepath = os.path.join(OBSIDIAN_VAULT_PATH, filename)
    logger.debug(f"Target file path resolved to: '{filepath}'")
    
    logger.debug("Assembling YAML frontmatter string configurations...")
    yaml_lines = [
        "---",
        "type: recipe",
        f'video_id: "{video_id}"',
        f'time_minutes: {recipe_data.get("time_minutes", 0)}',
        "components:"
    ]
    
    for comp in recipe_data.get("components", []):
        yaml_lines.append(f'  - name: "{comp.get("name", "Main")}"')
        yaml_lines.append(f'    ingredients:')
        for ing in comp.get("ingredients", []):
            yaml_lines.append(f'      - "[[{ing.title()}]]"')
            
    yaml_lines.append("---")
    yaml_lines.append(f"\n# {title}")
    yaml_lines.append(f"\n[Watch Source Video](https://youtube.com/watch?v={video_id})")
    
    logger.debug(f"Writing file out to disk using UTF-8 encoding scheme...")
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines))
        
    logger.info(f"Saved custom Markdown page to Obsidian Vault: '{filename}'")

# ==========================================
# 5. PIPELINE EXECUTION
# ==========================================
# ==========================================
# 5. PIPELINE EXECUTION (FIXED FOR PAGINATION)
# ==========================================
def main():
    logger.info("========= STARTING PANTRY PIPELINE IN DEBUG MODE =========")
    conn = init_db()
    cursor = conn.cursor()
    
    logger.debug(f"Verifying existence of target vault folder: '{OBSIDIAN_VAULT_PATH}'")
    os.makedirs(OBSIDIAN_VAULT_PATH, exist_ok=True)
    
    try:
        logger.info("Connecting to Todoist API to fetch remote projects list...")
        
        # FIX: Todoist API returns a ResultsPaginator (iterator of pages)
        project_paginator = todoist.get_projects()
        projects = []
        for page in project_paginator:
            projects.extend(page)
            
        logger.debug(f"Total remote projects fetched from Todoist: {len(projects)}")
        
        target_project = next((p for p in projects if p.name.lower() == PROJECT_NAME.lower()), None)
        if not target_project:
            logger.critical(f"Could not find a Todoist project named matching '{PROJECT_NAME}'. Pipeline aborted.")
            return
            
        logger.info(f"Target project identified (ID: {target_project.id}). Fetching pending tasks...")
        
        # FIX: Flatten task pagination into a standard list
        task_paginator = todoist.get_tasks(project_id=target_project.id)
        tasks = []
        for page in task_paginator:
            tasks.extend(page)
            
        logger.info(f"Queue Analysis: Found {len(tasks)} target links pending execution inside project.")
        
        for index, task in enumerate(tasks, start=1):
            logger.info(f"--- Processing Queue Item [{index}/{len(tasks)}]: '{task.content}' ---")
            
            # Step A: Identify Video ID
            video_id = extract_video_id(task.content) or extract_video_id(task.description)
            if not video_id:
                logger.warning(f"Task ID {task.id} skipped: Content formatting contains no legible 11-char YouTube ID.")
                continue
                
            # Step B: SQLite Duplication Check
            logger.debug(f"Querying SQLite registry ledger for video_id: {video_id}")
            cursor.execute("SELECT video_id FROM processed_videos WHERE video_id = ?", (video_id,))
            if cursor.fetchone():
                logger.info(f"Video {video_id} found in database. This task is a duplicate. Instructing Todoist to close task.")
                todoist.move_task(task.id)
                continue
                
            # Step C: Scraping Text
            transcript = get_transcript(video_id)
            if not transcript:
                logger.warning(f"Aborting execution loop for video {video_id}: Empty or missing transcript data stream.")
                continue
                
            # Step D: Hugging Face AI Call
            try:
                recipe_data = process_with_llm(transcript)
            except Exception as e:
                logger.error(f"Structured parser execution failed contextually for video {video_id}. Error details: {str(e)}")
                continue
                
            # Step E: Write File out
            save_to_obsidian(video_id, recipe_data)
            
            # Step F: Commit & Clean Remote Task Queue
            logger.debug(f"Logging unique key {video_id} into SQLite local 'processed_videos' table...")
            cursor.execute("INSERT INTO processed_videos (video_id, status) VALUES (?, ?)", (video_id, "done"))
            conn.commit()
            logger.debug("Database transaction successfully committed.")
            
            logger.info(f"Sending closure verification signal back to Todoist for Task ID: {task.id}")
            todoist.close_task(task_id=task.id)
            logger.info(f"Task tracking successfully finalized for item: {video_id}")
            
    except Exception as e:
        logger.critical(f"Fatal crash inside pipeline iteration loops: {str(e)}", exc_info=True)
    finally:
        logger.debug("Closing persistent connection handles to SQLite.")
        conn.close()
        logger.info("========= PANTRY PIPELINE EXECUTION TERMINATED =========")

if __name__ == "__main__":
    main()
import flet as ft
import requests
import json
import datetime
import re
import os
import base64
import random 
import time
import threading
import urllib.parse 
from dotenv import load_dotenv

# --- ABSOLUTE CLOUD PATHING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
NOTES_DIR = os.path.join(ASSETS_DIR, "saved_notes")
EXPORTS_DIR = os.path.join(ASSETS_DIR, "exports")
UPLOADS_DIR = os.path.join(ASSETS_DIR, "uploads")

# ---------------------------------------------------------
# 1. SECURE CONFIGURATION
# ---------------------------------------------------------
load_dotenv() 

API_KEY = os.getenv("GITHUB_API_KEY") 
MODEL_NAME = "gpt-4o-mini" 

AZURE_API_URL = "https://models.inference.ai.azure.com/chat/completions".strip("[]'\" \n\r")

CLOUD_DATA = {
    "Operating Systems (Theory)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/OS/os.txt", 
        "img_base_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/main/semister5/OS/images", 
        "github_api_url": "https://api.github.com/repos/cubee-codes/EduNex-Data/contents/semister5/OS/images",
        "available_images": [],
        "is_online": False
    },
    "Software Testing (Theory)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/SFT/sft.txt", 
        "img_base_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/main/semister5/SFT/images", 
        "github_api_url": "https://api.github.com/repos/cubee-codes/EduNex-Data/contents/semister5/SFT/images",
        "available_images": [],
        "is_online": False
    },
    "Emerging Trends in IT (Online Exam)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/main/semister6/ETI/eti.txt", 
        "img_base_url": "", 
        "github_api_url": "",
        "available_images": [],
        "is_online": True 
    }
}

# ---------------------------------------------------------
# 2. ULTRA-FAST SYLLABUS RAG ENGINE
# ---------------------------------------------------------
def fast_search_syllabus(query, chunks, top_k=5, randomize_if_empty=False):
    if not chunks: return "No syllabus context available."
    query_words = set(re.findall(r'\w+', query.lower()))
    
    if not query_words or randomize_if_empty: 
        sampled_chunks = random.sample(chunks, min(top_k, len(chunks)))
        return "\n\n--- RANDOM SYLLABUS EXCERPTS ---\n" + "\n...\n".join(sampled_chunks) + "\n----------------------------------\n"

    chunk_scores = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for q in query_words if q in chunk_lower)
        chunk_scores.append((score, chunk))
        
    chunk_scores.sort(key=lambda x: x[0], reverse=True)
    best_chunks = [c[1] for c in chunk_scores[:top_k] if c[0] > 0]
    
    if best_chunks: return "\n\n--- RELEVANT SYLLABUS EXCERPTS ---\n" + "\n...\n".join(best_chunks) + "\n----------------------------------\n"
    else: return "\n\n".join(chunks[:top_k])

# ---------------------------------------------------------
# 3. AI TRANSLATION LAYER
# ---------------------------------------------------------
def get_ai_response(user_input, is_exam_mode, chat_history_list, session_files, cached_syllabus_chunks, current_subject_key, is_quiz_mode=False, is_summary_mode=False, is_viva_mode=False, attached_file_path=None):
    if not API_KEY: return "❌ CRITICAL ERROR: GITHUB_API_KEY missing."
        
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    
    if attached_file_path and os.path.exists(attached_file_path):
        if len(session_files) >= 3: session_files.pop(0)
        ext = attached_file_path.lower().split('.')[-1]
        filename = os.path.basename(attached_file_path)
        if ext == 'txt':
            try:
                with open(attached_file_path, 'r', encoding='utf-8') as f:
                    session_files.append({"type": "text", "filename": filename, "content": f.read()})
            except Exception: pass
        elif ext in ['png', 'jpg', 'jpeg']:
            try:
                with open(attached_file_path, 'rb') as f:
                    file_data = base64.b64encode(f.read()).decode('utf-8')
                mime_type = f"image/{'jpeg' if ext == 'jpg' else ext}"
                session_files.append({"type": "binary", "filename": filename, "inline_data": {"mime_type": mime_type, "data": file_data}})
            except Exception: pass

    if is_quiz_mode or is_viva_mode or is_summary_mode:
        syllabus_context = fast_search_syllabus("", cached_syllabus_chunks, top_k=5, randomize_if_empty=True)
    else:
        syllabus_context = fast_search_syllabus(user_input, cached_syllabus_chunks)
        
    history_context = ""
    if chat_history_list and len(chat_history_list) > 0:
        recent_history = "".join(chat_history_list[-4:]) 
        history_context = f"\n--- RECENT CHAT HISTORY ---\n{recent_history}\n---------------------------\n"
        
    image_instruction = ""
    available_images = CLOUD_DATA[current_subject_key]["available_images"] if current_subject_key else []
    if available_images:
        image_instruction = f"\n\n--- LOCAL DIAGRAMS: {available_images} ---\n3. ONLY output exactly: [IMG: filename.png]\n"

    system_prompt = f"You are EduNex, an expert academic AI tutor.\n\nCONTEXT (Syllabus):\n{syllabus_context}"
    user_text_string = ""
    has_image = False
    image_list = []

    for f_obj in session_files:
        if f_obj["type"] == "text": user_text_string += f"\n\nFILE: {f_obj['content'][:4000]}\n"
        elif f_obj["type"] == "binary" and f_obj["inline_data"]["mime_type"].startswith("image/"):
            has_image = True
            image_list.append({"type": "image_url", "image_url": {"url": f"data:{f_obj['inline_data']['mime_type']};base64,{f_obj['inline_data']['data']}"}})

    concise_rule = "CRITICAL: Be extremely concise. Use plain text formatting. DO NOT use LaTeX."

    if is_quiz_mode: user_text_string += f"\n\nTASK: Generate 10 varied MCQs. Add Answer Key. {concise_rule}"
    elif is_viva_mode: user_text_string += f"\n\nTASK: Generate 15 Viva questions as 'Q: ' and 'A: '. {concise_rule}"
    elif is_summary_mode: user_text_string += f"\n\nTASK: Create a 'One-Page Cheat Sheet' for: {user_input}\n{image_instruction}\n{concise_rule}"
    else:
        style = "⚠️ EXAM MODE: Bullet points." if is_exam_mode else "🎓 TUTOR MODE: Deep explanation."
        user_text_string += f"\n\n{history_context}INSTRUCTION: {style}\n{image_instruction}\n{concise_rule}\nUSER INPUT: {user_input}"

    if has_image:
        image_guardrail = "CRITICAL VISION RULE: 1. If educational, analyze it. 2. If non-educational and user asks about it, reply EXACTLY: '⚠️ This image does not appear to be related to academic studies.' 3. If user asks general task, IGNORE the image.\n\n"
        user_text_string = image_guardrail + user_text_string
        user_message_content = [{"type": "text", "text": user_text_string}] + image_list
    else:
        user_message_content = user_text_string

    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message_content}],
        "temperature": 0.7 
    }

    try:
        response = requests.post(AZURE_API_URL, headers=headers, json=payload, timeout=(10.0, 30.0))
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0: return result['choices'][0]['message']['content']
        return f"❌ API Error {response.status_code}"
    except Exception as e: return f"Error: {str(e)}"

def extract_safe_json(raw_content):
    try:
        start = raw_content.find('{')
        end = raw_content.rfind('}') + 1
        if start != -1 and end != 0:
            return json.loads(raw_content[start:end])
        return None
    except:
        return None

def fetch_practice_question(cached_syllabus_chunks):
    syllabus_context = fast_search_syllabus("", cached_syllabus_chunks, top_k=6, randomize_if_empty=True)
    system_prompt = "You are a backend test generator. You ONLY output raw JSON. Do not add markdown blocks."
    user_prompt = f"""Based on this syllabus context, generate ONE unique, complex multiple-choice question. Do NOT reference diagrams.
    Context: {syllabus_context}
    
    Output EXACTLY in this JSON structure, nothing else:
    {{
        "question": "The question text here?",
        "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "answer_index": 0,
        "explanation": "Brief explanation of why this is correct."
    }}"""

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"model": MODEL_NAME, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.8}

    try:
        resp = requests.post(AZURE_API_URL, headers=headers, json=payload, timeout=15.0)
        if resp.status_code == 200:
            raw_content = resp.json()['choices'][0]['message']['content']
            return extract_safe_json(raw_content)
    except Exception as e:
        print("JSON Fetch Error:", e)
    return None

# ---------------------------------------------------------
# 4. THE APP UI
# ---------------------------------------------------------
def main(page: ft.Page):
    page.title = "EduNex Premium"
    
    page.theme = ft.Theme(color_scheme_seed=ft.colors.DEEP_PURPLE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.colors.DEEP_PURPLE)
    page.theme_mode = ft.ThemeMode.DARK 
    page.padding = 0

    premium_background = ft.Container(
        expand=True, 
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), 
            colors=["#0D1117", "#161B22", "#0D1117"] 
        )
    )

    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            premium_background.gradient = None
            premium_background.bgcolor = "#F4F6F9" 
        else:
            page.theme_mode = ft.ThemeMode.DARK
            premium_background.bgcolor = None
            premium_background.gradient = ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#0D1117", "#161B22", "#0D1117"]
            )
        page.update()

    theme_btn = ft.IconButton(icon=ft.icons.BRIGHTNESS_6, on_click=toggle_theme, tooltip="Toggle Light/Dark Mode")

    zoom_image = ft.Image(src="", fit=ft.ImageFit.CONTAIN, expand=True)
    zoom_dialog = ft.AlertDialog(content=ft.Container(content=zoom_image, width=800, height=600, padding=10), shape=ft.RoundedRectangleBorder(radius=10), actions=[ft.TextButton("Close", on_click=lambda e: (setattr(zoom_dialog, 'open', False), page.update()))])
    page.overlay.append(zoom_dialog)

    user_state = {"chat_history": [], "session_files": [], "current_subject": None, "cached_syllabus_chunks": [], "last_ai_response": None}
    
    main_screen = ft.Container(expand=True, visible=True)
    settings_screen = ft.Container(expand=True, visible=False)
    exam_screen = ft.Container(expand=True, visible=False, padding=20) 

    chat_history = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=20)
    current_subject_text = ft.Text("No Subject Selected", size=12, italic=True, color=ft.colors.ON_SURFACE_VARIANT)
    
    feedback_text = ft.Text("", size=13, weight="bold")
    status_row = ft.Row(controls=[feedback_text], alignment=ft.MainAxisAlignment.CENTER)

    search_box = ft.TextField(label="Search subject...", border_radius=8, text_size=14, prefix_icon=ft.icons.SEARCH)
    search_container = ft.Container(content=search_box, width=350)
    unified_dropdown = ft.Dropdown(label="Select Subject", border_radius=8, options=[ft.dropdown.Option(key) for key in CLOUD_DATA.keys()], width=350)
    mode_switch = ft.Switch(label="Exam Mode (Strict Constraints)", value=False)

    chat_box = ft.TextField(hint_text="Message EduNex...", border_radius=20, content_padding=15, expand=True, bgcolor=ft.colors.SURFACE, border_color=ft.colors.OUTLINE_VARIANT)
    send_button = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=ft.colors.PRIMARY, icon_size=24, tooltip="Send")

    def show_feedback(message, color=ft.colors.GREEN):
        feedback_text.value = message
        feedback_text.color = color
        page.update()
        def clear_text():
            time.sleep(3.5)
            if feedback_text.value == message: 
                feedback_text.value = ""
                try: page.update()
                except: pass
        threading.Thread(target=clear_text, daemon=True).start()

    # --- DOWNLOAD EXPORTERS ---
    def download_chat_history(e):
        if not user_state["chat_history"]:
            show_feedback("Chat is empty!", ft.colors.ORANGE)
            return
            
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EduNex_Chat_{timestamp}.txt"
        filepath = os.path.join(EXPORTS_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== EduNex Premium Chat Export ===\n")
            f.write(f"Subject: {user_state['current_subject']}\n")
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*34 + "\n\n")
            for msg in user_state["chat_history"]:
                clean_msg = re.sub(r'\[IMG:(.*?)\]', '[Diagram/Image removed in text export]', msg)
                f.write(clean_msg + "\n")
                
        page.launch_url(f"/exports/{filename}")
        show_feedback("Chat downloaded!", ft.colors.GREEN)

    def download_solved_mcqs(e):
        if not exam_state["answers"]:
            show_feedback("You haven't solved any questions yet!", ft.colors.ORANGE)
            return

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"EduNex_MCQ_{timestamp}.txt"
        filepath = os.path.join(EXPORTS_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"=== EduNex Solved Practice Exam ===\n")
            f.write(f"Subject: {user_state['current_subject']}\n")
            f.write(f"Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write("="*35 + "\n\n")
            
            for q_num, ans_idx in exam_state["answers"].items():
                if ans_idx is None: continue 
                data = exam_state["data"].get(q_num)
                if data:
                    correct_idx = data.get("answer_index", 0)
                    f.write(f"Question {q_num}: {data['question']}\n")
                    for i, opt in enumerate(data['options']):
                        f.write(f"   {chr(65+i)}) {opt}\n")
                    
                    if 0 <= ans_idx < len(data['options']):
                        f.write(f"\nYour Answer:    {chr(65+ans_idx)}) {data['options'][ans_idx]}\n")
                    if 0 <= correct_idx < len(data['options']):
                        f.write(f"Correct Answer: {chr(65+correct_idx)}) {data['options'][correct_idx]}\n")
                        
                    f.write(f"Explanation:    {data.get('explanation', '')}\n")
                    f.write("-" * 50 + "\n\n")
                    
        page.launch_url(f"/exports/{filename}")

    # --- INSTANT FEEDBACK EXAM MODULE ---
    exam_state = {"active": False, "current_q": 1, "total_q": 50, "answers": {}, "data": {}, "time_left": 3000, "selected_option": None} 
    
    exam_question_text = ft.Text("Loading question...", size=18, weight="w500")
    exam_options_column = ft.Column(spacing=10)
    exam_timer_text = ft.Text("50:00", size=32, weight="bold", color=ft.colors.PRIMARY)
    
    exam_grid_controls = []
    for i in range(1, 51):
        circle = ft.Container(content=ft.Text(str(i), size=11, color=ft.colors.ON_SURFACE_VARIANT), width=32, height=32, alignment=ft.alignment.center, border_radius=16, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), bgcolor=ft.colors.TRANSPARENT)
        exam_grid_controls.append(circle)
    exam_grid = ft.Row(controls=exam_grid_controls, wrap=True, width=280, spacing=8, run_spacing=8)

    exam_explanation_view = ft.ListView(expand=True, visible=False, padding=20)
    instant_feedback_view = ft.Column(visible=False, spacing=10)

    def format_time(seconds):
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def timer_thread():
        while exam_state["active"] and exam_state["time_left"] > 0:
            time.sleep(1)
            exam_state["time_left"] -= 1
            exam_timer_text.value = format_time(exam_state["time_left"])
            if exam_state["time_left"] < 300: exam_timer_text.color = ft.colors.ERROR
            try: page.update()
            except: pass
        if exam_state["time_left"] <= 0 and exam_state["active"]:
            finish_exam(None)

    def update_option_ui():
        for i, opt_container in enumerate(exam_options_column.controls):
            icon = opt_container.content.controls[0]
            if exam_state["selected_option"] == i:
                icon.name = ft.icons.RADIO_BUTTON_CHECKED
                icon.color = ft.colors.PRIMARY
                opt_container.bgcolor = ft.colors.SURFACE_VARIANT
            else:
                icon.name = ft.icons.RADIO_BUTTON_UNCHECKED
                icon.color = ft.colors.ON_SURFACE_VARIANT
                opt_container.bgcolor = ft.colors.TRANSPARENT
        page.update()

    def load_exam_question():
        try:
            exam_question_text.value = f"Q{exam_state['current_q']}: Fetching securely from syllabus..."
            exam_options_column.controls.clear()
            exam_state["selected_option"] = None
            exam_options_column.disabled = False
            
            instant_feedback_view.visible = False
            submit_btn.visible = True
            skip_btn.visible = True
            next_question_btn.visible = False
            page.update()
            
            # Fetch the question block
            q_data = fetch_practice_question(user_state["cached_syllabus_chunks"])
            
            # Bulletproof extraction to prevent silent thread crashes
            if not q_data or not isinstance(q_data, dict):
                q_data = {}
                
            q_text = q_data.get("question") or q_data.get("Question") or q_data.get("QUESTION") or "Network error fetching question. Please click Skip."
            
            raw_options = q_data.get("options") or q_data.get("Options") or q_data.get("choices") or q_data.get("Choices") or []
            if not isinstance(raw_options, list) or len(raw_options) == 0:
                raw_options = ["Error loading option A", "Error loading option B", "Error loading option C", "Error loading option D"]
                
            raw_ans = q_data.get("answer_index") or q_data.get("Answer_Index") or q_data.get("answer") or 0
            if isinstance(raw_ans, str) and raw_ans.isdigit(): raw_ans = int(raw_ans)
            if not isinstance(raw_ans, int): raw_ans = 0
            
            explanation = q_data.get("explanation") or q_data.get("Explanation") or "No explanation provided by AI."
            
            # Save the clean safe data back to memory
            safe_data = {
                "question": q_text,
                "options": raw_options,
                "answer_index": raw_ans,
                "explanation": explanation
            }
            
            exam_state["data"][exam_state["current_q"]] = safe_data
            exam_question_text.value = f"Q{exam_state['current_q']}. {safe_data['question']}"
            
            # Build buttons safely
            for idx, opt in enumerate(safe_data["options"]):
                def make_click_handler(i):
                    def handle_click(e):
                        if not exam_options_column.disabled:
                            exam_state["selected_option"] = i
                            update_option_ui()
                    return handle_click

                opt_row = ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, color=ft.colors.ON_SURFACE_VARIANT, size=20),
                        ft.Text(str(opt), expand=True, size=15)
                    ], vertical_alignment=ft.CrossAxisAlignment.START),
                    on_click=make_click_handler(idx),
                    border_radius=8,
                    padding=10,
                    cursor=ft.MouseCursor.CLICK,
                    bgcolor=ft.colors.TRANSPARENT
                )
                exam_options_column.controls.append(opt_row)
                
            page.update() 
            
        except Exception as e:
            # Absolute worst case scenario, show the error instead of crashing
            exam_question_text.value = f"System Parsing Error: {str(e)}. Please click Skip."
            exam_options_column.controls.clear()
            page.update()

    def submit_exam_answer(e):
        if exam_state["selected_option"] is None: 
            show_feedback("Please select an option first.", ft.colors.ORANGE)
            return
            
        q_num = exam_state["current_q"]
        user_ans = exam_state["selected_option"]
        exam_state["answers"][q_num] = user_ans
        
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.PRIMARY 
        exam_grid_controls[q_num - 1].content.color = ft.colors.ON_PRIMARY
        exam_grid_controls[q_num - 1].border = None
        
        data = exam_state["data"].get(q_num, {})
        correct_ans = data.get("answer_index", 0)
        is_correct = (user_ans == correct_ans)
        
        status_color = ft.colors.GREEN if is_correct else ft.colors.ERROR
        status_text = "✅ Correct!" if is_correct else "❌ Incorrect"
        
        instant_feedback_view.controls.clear()
        instant_feedback_view.controls.append(ft.Divider(height=20, color=ft.colors.TRANSPARENT))
        instant_feedback_view.controls.append(ft.Text(status_text, size=18, weight="bold", color=status_color))
        
        if not is_correct:
            if 0 <= correct_ans < len(data.get('options', [])):
                instant_feedback_view.controls.append(ft.Text(f"Correct Answer: {data['options'][correct_ans]}", weight="bold", color=ft.colors.GREEN))
            
        instant_feedback_view.controls.append(ft.Text(f"Explanation: {data.get('explanation', '')}", italic=True, color=ft.colors.ON_SURFACE_VARIANT))
        
        instant_feedback_view.visible = True
        exam_options_column.disabled = True
        submit_btn.visible = False
        skip_btn.visible = False
        next_question_btn.visible = True
        
        for i, opt_container in enumerate(exam_options_column.controls):
            if i == correct_ans:
                opt_container.border = ft.border.all(2, ft.colors.GREEN)
            elif i == user_ans and not is_correct:
                opt_container.border = ft.border.all(2, ft.colors.ERROR)
                
        page.update()

    def skip_exam_question(e):
        q_num = exam_state["current_q"]
        exam_state["answers"][q_num] = None 
        
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.SURFACE_VARIANT
        exam_grid_controls[q_num - 1].border = None
        
        data = exam_state["data"].get(q_num, {})
        correct_ans = data.get("answer_index", 0)
        
        instant_feedback_view.controls.clear()
        instant_feedback_view.controls.append(ft.Divider(height=20, color=ft.colors.TRANSPARENT))
        instant_feedback_view.controls.append(ft.Text("⏭️ Skipped", size=18, weight="bold", color=ft.colors.ORANGE))
        
        if 0 <= correct_ans < len(data.get('options', [])):
            instant_feedback_view.controls.append(ft.Text(f"Correct Answer: {data['options'][correct_ans]}", weight="bold", color=ft.colors.GREEN))
            
        instant_feedback_view.controls.append(ft.Text(f"Explanation: {data.get('explanation', '')}", italic=True, color=ft.colors.ON_SURFACE_VARIANT))
        
        instant_feedback_view.visible = True
        exam_options_column.disabled = True
        submit_btn.visible = False
        skip_btn.visible = False
        next_question_btn.visible = True
        
        if 0 <= correct_ans < len(exam_options_column.controls):
            exam_options_column.controls[correct_ans].border = ft.border.all(2, ft.colors.GREEN)
            
        page.update()
        
    def next_exam_question(e):
        q_num = exam_state["current_q"]
        if q_num < exam_state["total_q"]:
            exam_state["current_q"] += 1
            load_exam_question()
        else: 
            finish_exam(None)

    def finish_exam(e):
        exam_state["active"] = False
        exam_cards_row.visible = False 
        
        score = 0
        exam_explanation_view.controls.clear()
        exam_explanation_view.controls.append(ft.Text("Exam Results Summary", size=28, weight="bold", color=ft.colors.PRIMARY))
        
        for i in range(1, exam_state["current_q"] + 1):
            if i not in exam_state["data"]: continue
            data = exam_state["data"][i]
            user_ans = exam_state["answers"].get(i)
            correct_ans = data.get("answer_index", 0)
            is_correct = (user_ans == correct_ans)
            if is_correct: score += 1
            
            status_color = ft.colors.GREEN if is_correct else ft.colors.ERROR
            status_text = "Correct" if is_correct else ("Skipped" if user_ans is None else "Incorrect")
            
            correct_text = data['options'][correct_ans] if 0 <= correct_ans < len(data.get('options', [])) else "Unknown"
            
            exam_explanation_view.controls.append(
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([ft.Text(f"Question {i}", weight="bold", color=ft.colors.PRIMARY), ft.Text(status_text, color=status_color, weight="bold")]),
                            ft.Text(data.get('question', ''), size=15),
                            ft.Text(f"Correct Answer: {correct_text}", italic=True, color=ft.colors.ON_SURFACE_VARIANT),
                            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                            ft.Text(f"Explanation: {data.get('explanation', '')}", color=ft.colors.ON_SURFACE_VARIANT)
                        ])
                    )
                )
            )
            
        exam_explanation_view.controls.insert(1, ft.Row([
            ft.Text(f"Final Score: {score} / {exam_state['total_q']}", size=20, weight="bold"),
            ft.ElevatedButton("📥 Download Solved Q&A", on_click=download_solved_mcqs, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY))
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
        
        exam_explanation_view.visible = True
        page.update()

    def start_exam_mode(e):
        if not is_subject_loaded(): return
        main_screen.visible, exam_screen.visible = False, True
        exam_state.update({"active": True, "current_q": 1, "answers": {}, "data": {}, "time_left": 3000, "selected_option": None})
        
        exam_timer_text.color = ft.colors.PRIMARY
        exam_cards_row.visible = True 
        exam_explanation_view.visible = False
        
        for circle in exam_grid_controls: 
            circle.bgcolor = ft.colors.TRANSPARENT
            circle.border = ft.border.all(1, ft.colors.OUTLINE_VARIANT)
            circle.content.color = ft.colors.ON_SURFACE_VARIANT
            
        page.update()
        threading.Thread(target=timer_thread, daemon=True).start()
        threading.Thread(target=load_exam_question, daemon=True).start()

    submit_btn = ft.ElevatedButton("Submit Answer", on_click=submit_exam_answer, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)))
    skip_btn = ft.OutlinedButton("Skip Question", on_click=skip_exam_question, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    next_question_btn = ft.ElevatedButton("Next Question ➡", on_click=next_exam_question, visible=False, style=ft.ButtonStyle(bgcolor=ft.colors.GREEN_600, color=ft.colors.WHITE, shape=ft.RoundedRectangleBorder(radius=8)))
    end_test_btn = ft.TextButton("End Test Early", on_click=finish_exam, style=ft.ButtonStyle(color=ft.colors.ERROR))

    left_exam_card = ft.Card(
        elevation=2, expand=2,
        content=ft.Container(
            padding=30,
            content=ft.Column([
                exam_question_text, ft.Divider(height=20, color=ft.colors.TRANSPARENT), 
                exam_options_column, 
                instant_feedback_view,
                ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                ft.Row([
                    submit_btn, skip_btn, next_question_btn, ft.Container(expand=True), end_test_btn
                ])
            ])
        )
    )
    
    right_exam_card = ft.Card(
        elevation=2, expand=1,
        content=ft.Container(
            padding=30,
            content=ft.Column([
                ft.Text("Time Remaining", size=14, weight="w500", color=ft.colors.ON_SURFACE_VARIANT),
                exam_timer_text, ft.Divider(height=30),
                ft.Text("Question Progress", size=14, weight="w500", color=ft.colors.ON_SURFACE_VARIANT),
                ft.Container(height=10), exam_grid
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        )
    )

    exam_cards_row = ft.Row([left_exam_card, right_exam_card], expand=True, vertical_alignment=ft.CrossAxisAlignment.START)

    exam_screen.content = ft.Column([
        ft.Row([ft.TextButton("← Exit Practice", on_click=lambda e: go_home(e)), ft.Text("Online Practice Session", size=22, weight="bold", color=ft.colors.PRIMARY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        exam_cards_row,
        exam_explanation_view
    ])

    # --- FILE UPLOAD LOGIC ---
    attachment_text = ft.Text("", size=12, italic=True)
    active_attachment_path = None

    def cancel_upload(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        attachment_indicator.visible, chat_box.disabled, send_button.disabled = False, False, False
        show_feedback("Upload cancelled.", ft.colors.ERROR)
        page.update()

    def remove_attachment(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        user_state["session_files"] = [] 
        attachment_indicator.visible = False
        show_feedback("File cleared from AI memory.", ft.colors.ORANGE)
        page.update()

    cancel_btn = ft.TextButton("Cancel", on_click=cancel_upload, visible=False, style=ft.ButtonStyle(color=ft.colors.ERROR))
    remove_btn = ft.TextButton("Clear File", on_click=remove_attachment, visible=False)
    attachment_indicator = ft.Row([attachment_text, cancel_btn, remove_btn], alignment=ft.MainAxisAlignment.START, visible=False)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files:
            f = e.files[0]
            attachment_text.value = f"Uploading {f.name}..."
            cancel_btn.visible, remove_btn.visible, attachment_indicator.visible = True, False, True
            chat_box.disabled, send_button.disabled = True, True
            page.update()
            try:
                raw_url = page.get_upload_url(f.name, 60)
                parsed = urllib.parse.urlparse(raw_url)
                file_picker.upload([ft.FilePickerUploadFile(f.name, upload_url=f"{parsed.path}?{parsed.query}")])
            except Exception as ex:
                show_feedback(f"URL Error: {ex}", ft.colors.ERROR)
                chat_box.disabled, send_button.disabled = False, False
                page.update()

    def on_file_uploaded(e: ft.FilePickerUploadEvent):
        nonlocal active_attachment_path
        if e.error:
            show_feedback(f"Upload Failed: {e.error}", ft.colors.ERROR)
            cancel_btn.visible = False
        else:
            active_attachment_path = os.path.join(UPLOADS_DIR, e.file_name)
            attachment_text.value = f"📎 Attached: {e.file_name}"
            cancel_btn.visible, remove_btn.visible = False, True
            user_state["session_files"] = [] 
        chat_box.disabled, send_button.disabled = False, False
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_picked, on_upload=on_file_uploaded)
    page.overlay.append(file_picker)

    def go_settings(e):
        main_screen.visible, settings_screen.visible, exam_screen.visible = False, True, False
        page.update()

    def go_home(e):
        exam_state["active"] = False 
        main_screen.visible, settings_screen.visible, exam_screen.visible = True, False, False
        page.update()
    
    def add_message(text, is_user=False, is_quiz=False, is_summary=False, is_viva=False, has_attachment=False):
        sender = "You" if is_user else "EduNex"
        timestamp = datetime.datetime.now().strftime("%H:%M")
        user_state["chat_history"].append(f"[{timestamp}] {sender}:\n{text}\n" + "-"*40 + "\n")
        if not is_user: user_state["last_ai_response"] = text  
        if len(user_state["chat_history"]) > 10: user_state["chat_history"].pop(0)
        
        bg_color = ft.colors.SURFACE_VARIANT if not is_user else ft.colors.PRIMARY_CONTAINER
        text_color = ft.colors.ON_SURFACE_VARIANT if not is_user else ft.colors.ON_PRIMARY_CONTAINER

        message_elements = []
        if is_user:
            if has_attachment: message_elements.append(ft.Text("📎 File Included", size=12, italic=True, color=text_color))
            message_elements.append(ft.Text(text, size=15, color=text_color))
        else:
            parts = re.split(r'\[IMG:(.*?)\]', text)
            for i, part in enumerate(parts):
                part = part.strip()
                if not part: continue
                if i % 2 == 0: message_elements.append(ft.Markdown(part, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB))
                else:
                    curr_subj = user_state["current_subject"]
                    if curr_subj and curr_subj in CLOUD_DATA:
                        img_container = ft.Container(content=ft.Image(src=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", width=350, border_radius=10), data=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", on_click=lambda e: (setattr(zoom_image, 'src', e.control.data), setattr(zoom_dialog, 'open', True), page.update()))
                        message_elements.append(ft.Row([img_container], alignment=ft.MainAxisAlignment.CENTER))

        bubble = ft.Container(content=ft.Column(message_elements, spacing=10), bgcolor=bg_color, padding=15, border_radius=12, expand=True)
        chat_history.controls.append(ft.Container(ft.Row([ft.Container(width=50), bubble] if is_user else [bubble, ft.Container(width=50)], vertical_alignment=ft.CrossAxisAlignment.START), padding=5)) 
        chat_history.update()
        page.update()

    def execute_ai_task(msg, attached_file, is_quiz=False, is_summary=False, is_viva=False):
        chat_box.disabled, send_button.disabled = True, True
        loading_bubble = ft.Container(content=ft.Row([ft.ProgressRing(width=16, height=16), ft.Text(" Analyzing syllabus...", italic=True)]), padding=15)
        chat_history.controls.append(loading_bubble)
        page.update()
        
        def background_worker():
            try:
                resp = get_ai_response(msg, mode_switch.value, user_state["chat_history"], user_state["session_files"], user_state["cached_syllabus_chunks"], user_state["current_subject"], is_quiz, is_summary, is_viva, attached_file)
                if loading_bubble in chat_history.controls: chat_history.controls.remove(loading_bubble)
                add_message(str(resp), is_quiz=is_quiz, is_summary=is_summary, is_viva=is_viva)
            except Exception as e:
                if loading_bubble in chat_history.controls: chat_history.controls.remove(loading_bubble)
                show_feedback(f"System Fault: {str(e)}", ft.colors.ERROR)
            finally:
                chat_box.disabled, send_button.disabled = False, False
                page.update()
        threading.Thread(target=background_worker, daemon=True).start()

    def is_subject_loaded():
        if not user_state["current_subject"]: 
            show_feedback("Please select a subject from Configuration first!", ft.colors.ERROR)
            return False
        return True

    def send_click(e):
        nonlocal active_attachment_path
        if chat_box.disabled or (not chat_box.value and not active_attachment_path): return
        msg = chat_box.value
        chat_box.value = ""
        add_message(msg if msg else "Please analyze this file.", is_user=True, has_attachment=(active_attachment_path is not None))
        
        saved_path = active_attachment_path
        active_attachment_path = None
        if saved_path: attachment_text.value = f"📎 Image stored in AI Memory"
        page.update()
        execute_ai_task(msg, attached_file=saved_path)

    chat_box.on_submit = send_click
    send_button.on_click = send_click

    def action_click(e, mode):
        if not is_subject_loaded(): return
        add_message(f"Requested: {mode.title()}", is_user=True)
        execute_ai_task(e.control.data if mode == "summary" else "", None, is_quiz=(mode=="quiz"), is_summary=(mode=="summary"), is_viva=(mode=="viva"))

    theory_buttons = ft.Row([
        ft.OutlinedButton("🎯 Generate Quiz", on_click=lambda e: action_click(e, "quiz"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
        ft.OutlinedButton("🗣️ Viva Prep", on_click=lambda e: action_click(e, "viva"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    ], wrap=True)
    
    online_buttons = ft.Row([
        ft.ElevatedButton("📝 Start Online Practice Exam", on_click=start_exam_mode, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY, padding=20, shape=ft.RoundedRectangleBorder(radius=8)))
    ], alignment=ft.MainAxisAlignment.CENTER)

    action_buttons_container = ft.Container(content=theory_buttons)
    
    cheat_sheet_container = ft.Container(
        height=60, padding=10, 
        content=ft.Row(scroll="auto", controls=[
            ft.OutlinedButton(f"Unit {i} Summary", data=f"Unit {i}", on_click=lambda e: action_click(e, "summary"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20))) for i in range(1, 6)
        ])
    )

    def apply_settings_click(e):
        selected_name = unified_dropdown.value
        if not selected_name: return

        user_state["current_subject"] = selected_name
        current_subject_text.value = f"Connected: {selected_name}"
        
        if CLOUD_DATA[selected_name].get("is_online", False):
            action_buttons_container.content = online_buttons
            chat_box.disabled, send_button.disabled = False, False
            chat_box.hint_text = "Message EduNex (Practice Mode)..."
            cheat_sheet_container.visible = False
        else:
            action_buttons_container.content = theory_buttons
            chat_box.disabled, send_button.disabled = False, False
            chat_box.hint_text = "Message EduNex..."
            cheat_sheet_container.visible = True
            
        go_home(None)
        
        def fetch_cloud_data():
            if CLOUD_DATA[selected_name].get("txt_url"):
                try:
                    resp_txt = requests.get(CLOUD_DATA[selected_name]["txt_url"], timeout=5)
                    if resp_txt.status_code == 200: 
                        chunks = [resp_txt.text[i:i+1500] for i in range(0, len(resp_txt.text), 1500)]
                        user_state["cached_syllabus_chunks"] = chunks
                except Exception: pass
            show_feedback("Subject connected successfully!", ft.colors.GREEN)

        threading.Thread(target=fetch_cloud_data, daemon=True).start()

    main_screen.content = ft.Column(
        expand=True, spacing=0,
        controls=[
            ft.Container(padding=ft.padding.symmetric(horizontal=20, vertical=15), content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Row([ft.IconButton(ft.icons.MENU, on_click=go_settings), ft.Text("EduNex", size=24, weight="w900", color=ft.colors.PRIMARY), current_subject_text]), 
                ft.Row([theme_btn, ft.IconButton(ft.icons.DOWNLOAD_ROUNDED, tooltip="Download Chat", on_click=download_chat_history), ft.TextButton("Clear Chat", on_click=lambda e: chat_history.controls.clear() or page.update())])
            ])),
            ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
            cheat_sheet_container,
            ft.Container(content=status_row, height=20),
            ft.Container(content=chat_history, expand=True), 
            ft.Container(
                padding=20, bgcolor=ft.colors.SURFACE, border=ft.border.only(top=ft.border.BorderSide(1, ft.colors.OUTLINE_VARIANT)),
                content=ft.Column(spacing=10, controls=[
                    action_buttons_container, 
                    attachment_indicator,
                    ft.Row([ft.IconButton(ft.icons.ATTACH_FILE, on_click=lambda e: file_picker.pick_files(allowed_extensions=["txt", "png", "jpg", "jpeg"])), chat_box, send_button])
                ]) 
            )
        ]
    )

    settings_screen.content = ft.Column([
        ft.Container(padding=20, content=ft.Row([ft.IconButton(ft.icons.ARROW_BACK, on_click=go_home), ft.Text("Configuration", size=24, weight="bold")])),
        ft.Container(
            expand=True, alignment=ft.alignment.center,
            content=ft.Card(
                elevation=4,
                content=ft.Container(
                    width=450, padding=40,
                    content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=20, controls=[
                        ft.Icon(ft.icons.SETTINGS_SUGGEST, size=50, color=ft.colors.PRIMARY),
                        ft.Text("Subject Setup", size=22, weight="bold"),
                        ft.Divider(),
                        ft.Column([ft.Text("Select Module", weight="w500"), search_container, unified_dropdown], spacing=5),
                        ft.Divider(height=30, color=ft.colors.TRANSPARENT),
                        ft.Row([ft.Text("Strict Exam AI Mode", weight="w500"), mode_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                        ft.Divider(height=30, color=ft.colors.TRANSPARENT),
                        ft.ElevatedButton("Apply Configuration", on_click=apply_settings_click, width=350, height=50, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8)))
                    ])
                )
            )
        )
    ])

    page.add(ft.Stack(expand=True, controls=[premium_background, ft.Stack(expand=True, controls=[main_screen, settings_screen, exam_screen])]))

if __name__ == "__main__":
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    os.makedirs(NOTES_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.environ["FLET_SECRET_KEY"] = "EduNex_Secure_Key_2026"
    port = int(os.getenv("PORT", 8550))
    print(f"🌍 Starting EduNex Enterprise on port {port}...")
    ft.app(target=main, view="web_browser", port=port, host="0.0.0.0", assets_dir=ASSETS_DIR, upload_dir=UPLOADS_DIR)

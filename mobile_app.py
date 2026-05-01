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
import traceback
import urllib.parse 
from dotenv import load_dotenv

# --- ABSOLUTE CLOUD PATHING ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, "assets")
NOTES_DIR = os.path.join(ASSETS_DIR, "saved_notes")
EXPORTS_DIR = os.path.join(ASSETS_DIR, "exports")
UPLOADS_DIR = os.path.join(ASSETS_DIR, "uploads")

# ---------------------------------------------------------
# 1. SECURE CONFIGURATION (GITHUB MODELS API)
# ---------------------------------------------------------
load_dotenv() 

API_KEY = os.getenv("GITHUB_API_KEY") 
MODEL_NAME = "gpt-4o-mini" 

# --- UPDATED: Added is_online flag to distinguish subjects ---
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
    "Advanced Java (Online Exam Example)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/SFT/sft.txt", # Replace with actual URL
        "img_base_url": "", 
        "github_api_url": "",
        "available_images": [],
        "is_online": True # <--- THIS TRIGGERS THE PRACTICE MODULE
    }
}

# ---------------------------------------------------------
# 2. ULTRA-FAST SYLLABUS RAG ENGINE
# ---------------------------------------------------------
def fast_search_syllabus(query, chunks, top_k=5, randomize_if_empty=False):
    if not chunks: 
        return "No syllabus context available."
        
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
    
    if best_chunks:
        return "\n\n--- RELEVANT SYLLABUS EXCERPTS ---\n" + "\n...\n".join(best_chunks) + "\n----------------------------------\n"
    else:
        return "\n\n".join(chunks[:top_k])

# ---------------------------------------------------------
# 3. GITHUB MODELS API TRANSLATION LAYER
# ---------------------------------------------------------
def get_ai_response(user_input, is_exam_mode, chat_history_list, session_files, cached_syllabus_chunks, current_subject_key, is_quiz_mode=False, is_summary_mode=False, is_viva_mode=False, attached_file_path=None):
    if not API_KEY: return "❌ CRITICAL ERROR: GITHUB_API_KEY missing."
        
    url = "https://models.inference.ai.azure.com/chat/completions"
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

    if is_quiz_mode:
        user_text_string += f"\n\nTASK: Generate 10 varied MCQs. Add Answer Key. {concise_rule}"
    elif is_viva_mode:
        user_text_string += f"\n\nTASK: Generate 15 Viva questions as 'Q: ' and 'A: '. {concise_rule}"
    elif is_summary_mode:
        user_text_string += f"\n\nTASK: Create a 'One-Page Cheat Sheet' for: {user_input}\n{image_instruction}\n{concise_rule}"
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
        response = requests.post(url, headers=headers, json=payload, timeout=(10.0, 30.0))
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0: return result['choices'][0]['message']['content']
        return f"❌ API Error {response.status_code}"
    except Exception as e: return f"❌ Error: {str(e)}"

# --- NEW: DEDICATED JSON FETCHER FOR ONLINE EXAM ---
def fetch_practice_question(cached_syllabus_chunks):
    syllabus_context = fast_search_syllabus("", cached_syllabus_chunks, top_k=6, randomize_if_empty=True)
    
    system_prompt = "You are a backend test generator. You ONLY output raw JSON. Do not add markdown blocks like ```json."
    user_prompt = f"""Based on this syllabus context, generate ONE unique, complex multiple-choice question. Do NOT reference diagrams.
    Context: {syllabus_context}
    
    Output EXACTLY in this JSON structure, nothing else:
    {{
        "question": "The question text here?",
        "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
        "answer_index": 0,
        "explanation": "Brief explanation of why this is correct."
    }}"""

    url = "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {API_KEY}"}
    payload = {"model": MODEL_NAME, "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.8}

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15.0)
        if resp.status_code == 200:
            raw_content = resp.json()['choices'][0]['message']['content']
            clean_json = raw_content.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_json)
    except Exception as e:
        print("JSON Fetch Error:", e)
        return None

# ---------------------------------------------------------
# 4. THE APP UI
# ---------------------------------------------------------
def main(page: ft.Page):
    page.title = "EduNex Premium"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    # --- THEME TOGGLE LOGIC ---
    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            premium_background.gradient.colors = ["#f0f4f8", "#ffffff", "#e2e8f0"]
        else:
            page.theme_mode = ft.ThemeMode.DARK
            premium_background.gradient.colors = ["#0B0B13", "#1A1525", "#0F172A"]
        page.update()

    theme_btn = ft.IconButton(icon=ft.icons.BRIGHTNESS_6, on_click=toggle_theme, tooltip="Toggle Light/Dark Mode", icon_color=ft.colors.PRIMARY)

    # --- ZOOM MODAL SETUP ---
    zoom_image = ft.Image(src="", fit=ft.ImageFit.CONTAIN, expand=True)
    def close_zoom(e):
        zoom_dialog.open = False
        page.update()
    zoom_dialog = ft.AlertDialog(content=ft.Container(content=zoom_image, width=800, height=600, padding=10), shape=ft.RoundedRectangleBorder(radius=10), actions=[ft.ElevatedButton("Close", on_click=close_zoom)])
    page.overlay.append(zoom_dialog)

    def open_zoom(e):
        zoom_image.src = e.control.data
        zoom_dialog.open = True
        page.update()

    user_state = {
        "chat_history": [], "session_files": [], "current_subject": None, "cached_syllabus_chunks": [], "last_ai_response": None  
    }
    
    # --- SCREENS ---
    main_screen = ft.Container(expand=True, visible=True)
    settings_screen = ft.Container(expand=True, visible=False, padding=20)
    vault_screen = ft.Container(expand=True, visible=False, padding=20)
    exam_screen = ft.Container(expand=True, visible=False, padding=20) # NEW

    chat_history = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=15)
    current_subject_text = ft.Text("No Subject Selected", size=12, color="grey", italic=True)
    feedback_text = ft.Text("", size=12, weight="bold")
    status_row = ft.Row(controls=[feedback_text], alignment=ft.MainAxisAlignment.CENTER)
    
    search_box = ft.TextField(label="Type to search subject...", border_radius=10, text_size=14)
    search_container = ft.Container(content=search_box, width=300)
    unified_dropdown = ft.Dropdown(label="Select Subject", border_radius=10, options=[ft.dropdown.Option(key) for key in CLOUD_DATA.keys()], width=300)
    mode_switch = ft.Switch(label="Exam Mode (Strict)", value=False)

    vault_list = ft.ListView(expand=True, spacing=10)
    vault_viewer = ft.Column(expand=True, scroll="always", visible=False)

    chat_box = ft.TextField(hint_text="Ask a question...", border_radius=25, content_padding=15, expand=True)
    send_button = ft.ElevatedButton(content=ft.Text("➤", weight="bold"), style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=15))

    # --- EXAM MODULE STATE & UI ---
    exam_state = {"active": False, "current_q": 1, "total_q": 50, "answers": {}, "data": {}, "time_left": 3000} # 50 mins
    
    exam_question_text = ft.Text("Loading question...", size=18, weight="bold")
    exam_options = ft.RadioGroup(content=ft.Column([]))
    exam_timer_text = ft.Text("50:00", size=24, weight="bold", color="red")
    
    # Generate 50 circle indicators
    exam_grid_controls = []
    for i in range(1, 51):
        circle = ft.Container(content=ft.Text(str(i), size=12, color="white"), width=30, height=30, alignment=ft.alignment.center, border_radius=15, bgcolor=ft.colors.GREY_700)
        exam_grid_controls.append(circle)
    exam_grid = ft.Row(controls=exam_grid_controls, wrap=True, width=250)

    exam_explanation_view = ft.ListView(expand=True, visible=False)

    def format_time(seconds):
        mins, secs = divmod(seconds, 60)
        return f"{mins:02d}:{secs:02d}"

    def timer_thread():
        while exam_state["active"] and exam_state["time_left"] > 0:
            time.sleep(1)
            exam_state["time_left"] -= 1
            exam_timer_text.value = format_time(exam_state["time_left"])
            try: page.update()
            except: pass
        if exam_state["time_left"] <= 0 and exam_state["active"]:
            finish_exam(None)

    def load_exam_question():
        exam_question_text.value = f"Q{exam_state['current_q']}: Fetching from AI..."
        exam_options.content.controls.clear()
        page.update()
        
        q_data = fetch_practice_question(user_state["cached_syllabus_chunks"])
        if not q_data:
            q_data = {"question": "Network Error fetching question. Please Skip.", "options": ["Error", "Error", "Error", "Error"], "answer_index": 0, "explanation": "Failed to load."}
        
        exam_state["data"][exam_state["current_q"]] = q_data
        exam_question_text.value = f"Q{exam_state['current_q']}: {q_data['question']}"
        
        for idx, opt in enumerate(q_data["options"]):
            exam_options.content.controls.append(ft.Radio(value=str(idx), label=opt))
        exam_options.value = None
        page.update()

    def submit_exam_answer(e):
        if exam_options.value is None: return
        q_num = exam_state["current_q"]
        exam_state["answers"][q_num] = int(exam_options.value)
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.GREEN_600 # Mark Green
        
        if q_num < exam_state["total_q"]:
            exam_state["current_q"] += 1
            load_exam_question()
        else:
            finish_exam(None)

    def skip_exam_question(e):
        q_num = exam_state["current_q"]
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.BLUE_GREY_400 # Mark Gray
        if q_num < exam_state["total_q"]:
            exam_state["current_q"] += 1
            load_exam_question()
        else:
            finish_exam(None)

    def finish_exam(e):
        exam_state["active"] = False
        exam_question_text.value = "Exam Finished! Calculating Results..."
        exam_options.visible = False
        
        score = 0
        exam_explanation_view.controls.clear()
        exam_explanation_view.controls.append(ft.Text("Exam Results & Explanations", size=22, weight="bold", color=ft.colors.PRIMARY))
        
        for i in range(1, exam_state["current_q"] + 1):
            if i not in exam_state["data"]: continue
            data = exam_state["data"][i]
            user_ans = exam_state["answers"].get(i)
            correct_ans = data["answer_index"]
            
            is_correct = (user_ans == correct_ans)
            if is_correct: score += 1
            
            status_text = "✅ Correct" if is_correct else (f"❌ Incorrect (You skipped)" if user_ans is None else f"❌ Incorrect")
            
            exam_explanation_view.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Text(f"Q{i}: {data['question']}", weight="bold"),
                        ft.Text(status_text, color=ft.colors.GREEN if is_correct else ft.colors.RED),
                        ft.Text(f"Correct Answer: {data['options'][correct_ans]}", italic=True),
                        ft.Text(f"Explanation: {data['explanation']}", color=ft.colors.GREY_500)
                    ]),
                    padding=10, border=ft.border.all(1, ft.colors.OUTLINE), border_radius=8
                )
            )
            
        exam_explanation_view.controls.insert(1, ft.Text(f"Final Score: {score} / {exam_state['total_q']}", size=18, weight="bold"))
        exam_explanation_view.visible = True
        page.update()

    def start_exam_mode(e):
        if not is_subject_loaded(): return
        main_screen.visible, exam_screen.visible = False, True
        
        # Reset State
        exam_state.update({"active": True, "current_q": 1, "answers": {}, "data": {}, "time_left": 3000})
        for circle in exam_grid_controls: circle.bgcolor = ft.colors.GREY_700
        exam_options.visible = True
        exam_explanation_view.visible = False
        
        page.update()
        threading.Thread(target=timer_thread, daemon=True).start()
        threading.Thread(target=load_exam_question, daemon=True).start()

    # Layout for Exam Screen
    exam_screen.content = ft.Column([
        ft.Row([ft.ElevatedButton("← Leave Exam", on_click=lambda e: go_home(e)), ft.Text("Online Practice Module", size=20, weight="bold")], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        ft.Row([
            # Left Panel: Question
            ft.Container(
                content=ft.Column([exam_question_text, exam_options, ft.Row([ft.ElevatedButton("Submit Answer", on_click=submit_exam_answer, bgcolor=ft.colors.GREEN), ft.ElevatedButton("Skip", on_click=skip_exam_question), ft.ElevatedButton("End Test Early", on_click=finish_exam, bgcolor=ft.colors.RED)])]),
                expand=2
            ),
            # Right Panel: Timer & Grid
            ft.Container(
                content=ft.Column([ft.Text("Time Remaining", size=14), exam_timer_text, ft.Divider(), ft.Text("Question Panel", size=14), exam_grid], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                expand=1, padding=15, border=ft.border.all(1, ft.colors.OUTLINE), border_radius=10
            )
        ], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
        exam_explanation_view
    ])

    # --- FILE UPLOAD LOGIC ---
    attachment_text = ft.Text("", size=12, italic=True)
    active_attachment_path = None

    def cancel_upload(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        attachment_indicator.visible, chat_box.disabled, send_button.disabled = False, False, False
        show_feedback("❌ Upload cancelled.", color="red")
        page.update()

    def remove_attachment(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        user_state["session_files"] = [] 
        attachment_indicator.visible = False
        show_feedback("🗑️ File cleared from AI memory.", color="orange")
        page.update()

    cancel_btn = ft.ElevatedButton("❌ Cancel", on_click=cancel_upload, visible=False)
    remove_btn = ft.ElevatedButton("🗑️ Clear File", on_click=remove_attachment, visible=False)
    attachment_indicator = ft.Row([attachment_text, cancel_btn, remove_btn], alignment=ft.MainAxisAlignment.CENTER, visible=False)

    def on_file_picked(e: ft.FilePickerResultEvent):
        if e.files:
            f = e.files[0]
            attachment_text.value = f"⏳ Uploading {f.name}..."
            cancel_btn.visible, remove_btn.visible, attachment_indicator.visible = True, False, True
            chat_box.disabled, send_button.disabled = True, True
            page.update()
            try:
                raw_url = page.get_upload_url(f.name, 60)
                parsed = urllib.parse.urlparse(raw_url)
                file_picker.upload([ft.FilePickerUploadFile(f.name, upload_url=f"{parsed.path}?{parsed.query}")])
            except Exception as ex:
                show_feedback(f"❌ URL Error: {ex}", "red")
                chat_box.disabled, send_button.disabled = False, False
                page.update()

    def on_file_uploaded(e: ft.FilePickerUploadEvent):
        nonlocal active_attachment_path
        if e.error:
            attachment_text.value = f"❌ Upload Failed: {e.error}"
            cancel_btn.visible = False
        else:
            active_attachment_path = os.path.join(UPLOADS_DIR, e.file_name)
            attachment_text.value = f"✅ Attached: {e.file_name}"
            cancel_btn.visible, remove_btn.visible = False, True
            user_state["session_files"] = [] 
        chat_box.disabled, send_button.disabled = False, False
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_picked, on_upload=on_file_uploaded)
    page.overlay.append(file_picker)

    def show_feedback(message, color="green"):
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

    def go_settings(e):
        main_screen.visible, settings_screen.visible, vault_screen.visible, exam_screen.visible = False, True, False, False
        page.update()

    def go_home(e):
        exam_state["active"] = False # Stop timer if exiting exam
        main_screen.visible, settings_screen.visible, vault_screen.visible, exam_screen.visible = True, False, False, False
        page.update()
    
    def add_message(text, is_user=False, is_quiz=False, is_summary=False, is_viva=False, has_attachment=False):
        sender = "You" if is_user else "EduNex"
        timestamp = datetime.datetime.now().strftime("%H:%M")
        user_state["chat_history"].append(f"[{timestamp}] {sender}:\n{text}\n" + "-"*40 + "\n")
        if not is_user: user_state["last_ai_response"] = text  
        if len(user_state["chat_history"]) > 10: user_state["chat_history"].pop(0)
        
        bg_color = ft.colors.SURFACE_VARIANT if not is_user else ft.colors.INVERSE_SURFACE 

        message_elements = []
        if is_user:
            if has_attachment: message_elements.append(ft.Text("📎 [File Processed]", size=12, italic=True))
            message_elements.append(ft.Text(text, size=15))
        else:
            parts = re.split(r'\[IMG:(.*?)\]', text)
            for i, part in enumerate(parts):
                part = part.strip()
                if not part: continue
                if i % 2 == 0: message_elements.append(ft.Markdown(part, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB))
                else:
                    curr_subj = user_state["current_subject"]
                    if curr_subj and curr_subj in CLOUD_DATA:
                        img_container = ft.Container(content=ft.Image(src=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", width=350, border_radius=10), data=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", on_click=open_zoom)
                        message_elements.append(ft.Row([img_container], alignment=ft.MainAxisAlignment.CENTER))

        bubble = ft.Container(content=ft.Column(message_elements, spacing=10), bgcolor=bg_color, padding=15, border_radius=10, expand=True)
        chat_history.controls.append(ft.Container(ft.Row([ft.Container(width=50), bubble] if is_user else [bubble, ft.Container(width=50)], vertical_alignment=ft.CrossAxisAlignment.START), padding=5)) 
        chat_history.update()
        page.update()

    def execute_ai_task(msg, attached_file, is_quiz=False, is_summary=False, is_viva=False):
        chat_box.disabled, send_button.disabled = True, True
        loading_bubble = ft.Container(content=ft.Row([ft.ProgressRing(width=16, height=16), ft.Text(" AI is analyzing...", italic=True)]), padding=15, border_radius=10)
        chat_history.controls.append(loading_bubble)
        page.update()
        
        def background_worker():
            try:
                resp = get_ai_response(msg, mode_switch.value, user_state["chat_history"], user_state["session_files"], user_state["cached_syllabus_chunks"], user_state["current_subject"], is_quiz, is_summary, is_viva, attached_file)
                if loading_bubble in chat_history.controls: chat_history.controls.remove(loading_bubble)
                add_message(str(resp), is_quiz=is_quiz, is_summary=is_summary, is_viva=is_viva)
            except Exception as e:
                if loading_bubble in chat_history.controls: chat_history.controls.remove(loading_bubble)
                add_message(f"❌ System Fault: {str(e)}")
            finally:
                chat_box.disabled, send_button.disabled = False, False
                page.update()
        threading.Thread(target=background_worker, daemon=True).start()

    def is_subject_loaded():
        if not user_state["current_subject"]: show_feedback("⚠️ Please select a subject from Configuration first!", "red"); return False
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
        add_message(f"Request: {mode}", is_user=True)
        execute_ai_task(e.control.data if mode == "summary" else "", None, is_quiz=(mode=="quiz"), is_summary=(mode=="summary"), is_viva=(mode=="viva"))

    # Dynamic Action Buttons Container
    theory_buttons = ft.Row([
        ft.ElevatedButton("🎯 Quiz", on_click=lambda e: action_click(e, "quiz")),
        ft.ElevatedButton("🗣️ Viva", on_click=lambda e: action_click(e, "viva")),
        ft.ElevatedButton("⭐ Mark", on_click=lambda e: show_feedback("Feature in development", "orange"))
    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY, wrap=True)
    
    online_buttons = ft.Row([
        ft.ElevatedButton("📝 Start Online Practice Exam", on_click=start_exam_mode, bgcolor=ft.colors.BLUE, color=ft.colors.WHITE, width=300, height=45)
    ], alignment=ft.MainAxisAlignment.CENTER)

    action_buttons_container = ft.Container(content=theory_buttons)

    def apply_settings_click(e):
        selected_name = unified_dropdown.value
        if not selected_name: return

        user_state["current_subject"] = selected_name
        current_subject_text.value = f"Connecting to {selected_name}..."
        
        # --- UI SHIFT FOR ONLINE EXAMS ---
        if CLOUD_DATA[selected_name].get("is_online", False):
            action_buttons_container.content = online_buttons
            chat_box.disabled = True # Disable chat for online exam mode
            send_button.disabled = True
            chat_box.hint_text = "Chat is disabled in Online Exam Mode."
        else:
            action_buttons_container.content = theory_buttons
            chat_box.disabled = False
            send_button.disabled = False
            chat_box.hint_text = "Ask a question..."
            
        go_home(None)
        
        def fetch_cloud_data():
            if CLOUD_DATA[selected_name].get("txt_url"):
                try:
                    resp_txt = requests.get(CLOUD_DATA[selected_name]["txt_url"], timeout=5)
                    if resp_txt.status_code == 200: 
                        chunks = [resp_txt.text[i:i+1500] for i in range(0, len(resp_txt.text), 1500)]
                        user_state["cached_syllabus_chunks"] = chunks
                except Exception: pass
            current_subject_text.value = f"Selected: {selected_name} ☁️"
            show_feedback("✅ Applied Settings!", "green")
            page.update()

        threading.Thread(target=fetch_cloud_data, daemon=True).start()

    main_screen.content = ft.Column(
        expand=True, spacing=0,
        controls=[
            ft.Container(padding=10, content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Row([ft.ElevatedButton("☰", on_click=go_settings), ft.Text("EduNex 2.0", size=20, weight="bold", color=ft.colors.PRIMARY)]), 
                ft.ElevatedButton("Clear", on_click=lambda e: chat_history.controls.clear() or page.update())
            ])),
            ft.Container(content=current_subject_text, padding=10),
            ft.Container(content=status_row, height=20),
            ft.Container(height=45, padding=10, content=ft.Row(scroll="always", controls=[ft.ElevatedButton(f"Unit {i}", data=f"Unit {i}", on_click=lambda e: action_click(e, "summary")) for i in range(1, 6)])),
            ft.Divider(),
            ft.Container(content=chat_history, expand=True), 
            ft.Container(
                padding=15, bgcolor=ft.colors.SURFACE_VARIANT, border_radius=ft.border_radius.only(top_left=25, top_right=25),
                content=ft.Column([
                    action_buttons_container, 
                    ft.Container(content=attachment_indicator, padding=10),
                    ft.Row([ft.ElevatedButton("Upload", on_click=lambda e: file_picker.pick_files(allowed_extensions=["txt", "png", "jpg", "jpeg"])), chat_box, send_button])
                ]) 
            )
        ]
    )

    settings_screen.content = ft.Column([
        ft.Container(height=20),
        ft.Row([ft.ElevatedButton("← Back", on_click=go_home), ft.Text("Configuration", size=22, weight="bold"), ft.Container(expand=True), theme_btn]),
        ft.Divider(),
        ft.Container(expand=True, content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, scroll="always", controls=[
            ft.Text("🔎 Find Subject", weight="bold"), search_container, unified_dropdown, ft.Container(height=30),
            ft.Text("🧠 AI Personality", weight="bold"), mode_switch, ft.Container(height=30),
            ft.ElevatedButton("APPLY CHANGES", on_click=apply_settings_click, width=300, height=50)
        ]))
    ])

    vault_screen.content = ft.Column([ft.Row([ft.ElevatedButton("← Back", on_click=go_home), ft.Text("Vault", size=22)]), ft.Divider(), vault_list, vault_viewer])

    premium_background = ft.Container(expand=True, gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#0B0B13", "#1A1525", "#0F172A"]))

    page.add(ft.Stack(expand=True, controls=[premium_background, ft.Stack(expand=True, controls=[main_screen, settings_screen, vault_screen, exam_screen])]))

if __name__ == "__main__":
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    os.makedirs(NOTES_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.environ["FLET_SECRET_KEY"] = "EduNex_Secure_Key_2026"
    port = int(os.getenv("PORT", 8550))
    print(f"🌍 Starting EduNex 2.0 Web Server on port {port}...")
    ft.app(target=main, view="web_browser", port=port, host="0.0.0.0", assets_dir=ASSETS_DIR, upload_dir=UPLOADS_DIR)

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
    "Advanced Java (Online Exam)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/SFT/sft.txt", 
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
        response = requests.post(url, headers=headers, json=payload, timeout=(10.0, 30.0))
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0: return result['choices'][0]['message']['content']
        return f"❌ API Error {response.status_code}"
    except Exception as e: return f"❌ Error: {str(e)}"

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
# 4. THE APP UI (PROFESSIONAL OVERHAUL)
# ---------------------------------------------------------
def main(page: ft.Page):
    page.title = "EduNex Premium"
    
    # --- PROFESSIONAL PURPLE THEME ---
    page.theme = ft.Theme(color_scheme_seed=ft.colors.DEEP_PURPLE)
    page.dark_theme = ft.Theme(color_scheme_seed=ft.colors.DEEP_PURPLE)
    page.theme_mode = ft.ThemeMode.DARK 
    page.padding = 0

    premium_background = ft.Container(
        expand=True, 
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), 
            colors=["#0A0612", "#130D26", "#0A0612"] # Sleek obsidian purple
        )
    )

    def toggle_theme(e):
        if page.theme_mode == ft.ThemeMode.DARK:
            page.theme_mode = ft.ThemeMode.LIGHT
            premium_background.gradient = None
            premium_background.bgcolor = "#F4F6F9" # Crisp modern light grey
        else:
            page.theme_mode = ft.ThemeMode.DARK
            premium_background.bgcolor = None
            premium_background.gradient = ft.LinearGradient(
                begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1), colors=["#0A0612", "#130D26", "#0A0612"]
            )
        page.update()

    theme_btn = ft.IconButton(icon=ft.icons.BRIGHTNESS_6, on_click=toggle_theme, tooltip="Toggle Light/Dark Mode")

    # --- ZOOM MODAL ---
    zoom_image = ft.Image(src="", fit=ft.ImageFit.CONTAIN, expand=True)
    zoom_dialog = ft.AlertDialog(content=ft.Container(content=zoom_image, width=800, height=600, padding=10), shape=ft.RoundedRectangleBorder(radius=10), actions=[ft.TextButton("Close", on_click=lambda e: (setattr(zoom_dialog, 'open', False), page.update()))])
    page.overlay.append(zoom_dialog)

    user_state = {"chat_history": [], "session_files": [], "current_subject": None, "cached_syllabus_chunks": [], "last_ai_response": None}
    
    main_screen = ft.Container(expand=True, visible=True)
    settings_screen = ft.Container(expand=True, visible=False)
    vault_screen = ft.Container(expand=True, visible=False, padding=20)
    exam_screen = ft.Container(expand=True, visible=False, padding=20) 

    chat_history = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=20)
    current_subject_text = ft.Text("No Subject Selected", size=12, italic=True, color=ft.colors.ON_SURFACE_VARIANT)
    
    search_box = ft.TextField(label="Search subject...", border_radius=8, text_size=14, prefix_icon=ft.icons.SEARCH)
    search_container = ft.Container(content=search_box, width=350)
    unified_dropdown = ft.Dropdown(label="Select Subject", border_radius=8, options=[ft.dropdown.Option(key) for key in CLOUD_DATA.keys()], width=350)
    mode_switch = ft.Switch(label="Exam Mode (Strict Constraints)", value=False)

    vault_list = ft.ListView(expand=True, spacing=10)
    vault_viewer = ft.Column(expand=True, scroll="always", visible=False)

    chat_box = ft.TextField(hint_text="Message EduNex...", border_radius=20, content_padding=15, expand=True, bgcolor=ft.colors.SURFACE, border_color=ft.colors.OUTLINE_VARIANT)
    send_button = ft.IconButton(icon=ft.icons.SEND_ROUNDED, icon_color=ft.colors.PRIMARY, icon_size=24, tooltip="Send")

    # --- EXAM MODULE (PROFESSIONAL LAYOUT) ---
    exam_state = {"active": False, "current_q": 1, "total_q": 50, "answers": {}, "data": {}, "time_left": 3000} 
    
    exam_question_text = ft.Text("Loading question...", size=18, weight="w500")
    exam_options = ft.RadioGroup(content=ft.Column(spacing=15))
    exam_timer_text = ft.Text("50:00", size=32, weight="bold", color=ft.colors.PRIMARY)
    
    exam_grid_controls = []
    for i in range(1, 51):
        circle = ft.Container(content=ft.Text(str(i), size=11, color=ft.colors.ON_SURFACE_VARIANT), width=32, height=32, alignment=ft.alignment.center, border_radius=16, border=ft.border.all(1, ft.colors.OUTLINE_VARIANT), bgcolor=ft.colors.TRANSPARENT)
        exam_grid_controls.append(circle)
    exam_grid = ft.Row(controls=exam_grid_controls, wrap=True, width=280, spacing=8, run_spacing=8)

    exam_explanation_view = ft.ListView(expand=True, visible=False, padding=20)

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

    def load_exam_question():
        exam_question_text.value = f"Q{exam_state['current_q']}: Fetching securely from syllabus..."
        exam_options.content.controls.clear()
        page.update()
        
        q_data = fetch_practice_question(user_state["cached_syllabus_chunks"])
        if not q_data:
            q_data = {"question": "Network Error fetching question. Please Skip.", "options": ["Error", "Error", "Error", "Error"], "answer_index": 0, "explanation": "Failed to load due to API timeout."}
        
        exam_state["data"][exam_state["current_q"]] = q_data
        exam_question_text.value = f"Q{exam_state['current_q']}. {q_data['question']}"
        
        for idx, opt in enumerate(q_data["options"]):
            exam_options.content.controls.append(ft.Radio(value=str(idx), label=opt))
        exam_options.value = None
        page.update()

    def submit_exam_answer(e):
        if exam_options.value is None: return
        q_num = exam_state["current_q"]
        exam_state["answers"][q_num] = int(exam_options.value)
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.PRIMARY 
        exam_grid_controls[q_num - 1].content.color = ft.colors.ON_PRIMARY
        exam_grid_controls[q_num - 1].border = None
        
        if q_num < exam_state["total_q"]:
            exam_state["current_q"] += 1
            load_exam_question()
        else: finish_exam(None)

    def skip_exam_question(e):
        q_num = exam_state["current_q"]
        exam_grid_controls[q_num - 1].bgcolor = ft.colors.SURFACE_VARIANT
        exam_grid_controls[q_num - 1].border = None
        if q_num < exam_state["total_q"]:
            exam_state["current_q"] += 1
            load_exam_question()
        else: finish_exam(None)

    def finish_exam(e):
        exam_state["active"] = False
        left_exam_card.visible, right_exam_card.visible = False, False
        
        score = 0
        exam_explanation_view.controls.clear()
        exam_explanation_view.controls.append(ft.Text("Exam Results Summary", size=28, weight="bold", color=ft.colors.PRIMARY))
        
        for i in range(1, exam_state["current_q"] + 1):
            if i not in exam_state["data"]: continue
            data = exam_state["data"][i]
            user_ans = exam_state["answers"].get(i)
            correct_ans = data["answer_index"]
            is_correct = (user_ans == correct_ans)
            if is_correct: score += 1
            
            status_color = ft.colors.GREEN if is_correct else ft.colors.ERROR
            status_text = "Correct" if is_correct else ("Skipped" if user_ans is None else "Incorrect")
            
            exam_explanation_view.controls.append(
                ft.Card(
                    elevation=1,
                    content=ft.Container(
                        padding=20,
                        content=ft.Column([
                            ft.Row([ft.Text(f"Question {i}", weight="bold", color=ft.colors.PRIMARY), ft.Text(status_text, color=status_color, weight="bold")]),
                            ft.Text(data['question'], size=15),
                            ft.Text(f"Correct Answer: {data['options'][correct_ans]}", italic=True, color=ft.colors.ON_SURFACE_VARIANT),
                            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                            ft.Text(f"Explanation: {data['explanation']}", color=ft.colors.ON_SURFACE_VARIANT)
                        ])
                    )
                )
            )
            
        exam_explanation_view.controls.insert(1, ft.Text(f"Final Score: {score} / {exam_state['total_q']}", size=20, weight="bold"))
        exam_explanation_view.visible = True
        page.update()

    def start_exam_mode(e):
        if not is_subject_loaded(): return
        main_screen.visible, exam_screen.visible = False, True
        exam_state.update({"active": True, "current_q": 1, "answers": {}, "data": {}, "time_left": 3000})
        
        exam_timer_text.color = ft.colors.PRIMARY
        left_exam_card.visible, right_exam_card.visible = True, True
        exam_explanation_view.visible = False
        
        for circle in exam_grid_controls: 
            circle.bgcolor = ft.colors.TRANSPARENT
            circle.border = ft.border.all(1, ft.colors.OUTLINE_VARIANT)
            circle.content.color = ft.colors.ON_SURFACE_VARIANT
            
        page.update()
        threading.Thread(target=timer_thread, daemon=True).start()
        threading.Thread(target=load_exam_question, daemon=True).start()

    # --- PROFESSIONAL EXAM CARDS ---
    left_exam_card = ft.Card(
        elevation=2, expand=2,
        content=ft.Container(
            padding=30,
            content=ft.Column([
                exam_question_text, ft.Divider(height=20, color=ft.colors.TRANSPARENT), exam_options, ft.Divider(height=20, color=ft.colors.TRANSPARENT),
                ft.Row([
                    ft.ElevatedButton("Submit Answer", on_click=submit_exam_answer, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY, shape=ft.RoundedRectangleBorder(radius=8))),
                    ft.OutlinedButton("Skip Question", on_click=skip_exam_question, style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
                    ft.Container(expand=True),
                    ft.TextButton("End Test Early", on_click=finish_exam, style=ft.ButtonStyle(color=ft.colors.ERROR))
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

    exam_screen.content = ft.Column([
        ft.Row([ft.TextButton("← Exit Practice", on_click=lambda e: go_home(e)), ft.Text("Online Practice Session", size=22, weight="bold", color=ft.colors.PRIMARY)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ft.Divider(),
        ft.Row([left_exam_card, right_exam_card], expand=True, vertical_alignment=ft.CrossAxisAlignment.START),
        exam_explanation_view
    ])

    # --- FILE UPLOAD LOGIC ---
    attachment_text = ft.Text("", size=12, italic=True)
    active_attachment_path = None

    def cancel_upload(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        attachment_indicator.visible, chat_box.disabled, send_button.disabled = False, False, False
        page.snack_bar = ft.SnackBar(ft.Text("Upload cancelled."), bgcolor=ft.colors.ERROR)
        page.snack_bar.open = True
        page.update()

    def remove_attachment(e):
        nonlocal active_attachment_path
        active_attachment_path = None
        user_state["session_files"] = [] 
        attachment_indicator.visible = False
        page.snack_bar = ft.SnackBar(ft.Text("File cleared from AI memory."))
        page.snack_bar.open = True
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
                page.snack_bar = ft.SnackBar(ft.Text(f"URL Error: {ex}"), bgcolor=ft.colors.ERROR)
                page.snack_bar.open, chat_box.disabled, send_button.disabled = True, False, False
                page.update()

    def on_file_uploaded(e: ft.FilePickerUploadEvent):
        nonlocal active_attachment_path
        if e.error:
            page.snack_bar = ft.SnackBar(ft.Text(f"Upload Failed: {e.error}"), bgcolor=ft.colors.ERROR)
            page.snack_bar.open, cancel_btn.visible = True, False
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
        main_screen.visible, settings_screen.visible, vault_screen.visible, exam_screen.visible = False, True, False, False
        page.update()

    def go_home(e):
        exam_state["active"] = False 
        main_screen.visible, settings_screen.visible, vault_screen.visible, exam_screen.visible = True, False, False, False
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
                        img_container = ft.Container(content=ft.Image(src=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", width=350, border_radius=10), data=f"{CLOUD_DATA[curr_subj]['img_base_url']}/{urllib.parse.quote(part)}", on_click=lambda e: (setattr(zoom_image, 'src', e.control.data), setattr(zoom_dialog, 'open', True), page.update()), cursor=ft.MouseCursor.CLICK)
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
                page.snack_bar = ft.SnackBar(ft.Text(f"System Fault: {str(e)}"), bgcolor=ft.colors.ERROR)
                page.snack_bar.open = True
            finally:
                chat_box.disabled, send_button.disabled = False, False
                page.update()
        threading.Thread(target=background_worker, daemon=True).start()

    def is_subject_loaded():
        if not user_state["current_subject"]: 
            page.snack_bar = ft.SnackBar(ft.Text("Please select a subject from Configuration first!"), bgcolor=ft.colors.ERROR)
            page.snack_bar.open = True
            page.update()
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

    # --- PROFESSIONAL MAIN CHAT ALIGNMENT ---
    theory_buttons = ft.Row([
        ft.OutlinedButton("🎯 Generate Quiz", on_click=lambda e: action_click(e, "quiz"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
        ft.OutlinedButton("🗣️ Viva Prep", on_click=lambda e: action_click(e, "viva"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8))),
        ft.OutlinedButton("⭐ Bookmark Note", on_click=lambda e: (setattr(page, 'snack_bar', ft.SnackBar(ft.Text("Feature in development"))), setattr(page.snack_bar, 'open', True), page.update()), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)))
    ], wrap=True)
    
    online_buttons = ft.Row([
        ft.ElevatedButton("📝 Start Online Practice Exam", on_click=start_exam_mode, style=ft.ButtonStyle(bgcolor=ft.colors.PRIMARY, color=ft.colors.ON_PRIMARY, padding=20, shape=ft.RoundedRectangleBorder(radius=8)))
    ], alignment=ft.MainAxisAlignment.CENTER)

    action_buttons_container = ft.Container(content=theory_buttons)

    def apply_settings_click(e):
        selected_name = unified_dropdown.value
        if not selected_name: return

        user_state["current_subject"] = selected_name
        current_subject_text.value = f"Connected: {selected_name}"
        
        if CLOUD_DATA[selected_name].get("is_online", False):
            action_buttons_container.content = online_buttons
            chat_box.disabled, send_button.disabled = True, True
            chat_box.hint_text = "Chat is disabled in Online Exam Mode."
        else:
            action_buttons_container.content = theory_buttons
            chat_box.disabled, send_button.disabled = False, False
            chat_box.hint_text = "Message EduNex..."
            
        go_home(None)
        
        def fetch_cloud_data():
            if CLOUD_DATA[selected_name].get("txt_url"):
                try:
                    resp_txt = requests.get(CLOUD_DATA[selected_name]["txt_url"], timeout=5)
                    if resp_txt.status_code == 200: 
                        chunks = [resp_txt.text[i:i+1500] for i in range(0, len(resp_txt.text), 1500)]
                        user_state["cached_syllabus_chunks"] = chunks
                except Exception: pass
            page.snack_bar = ft.SnackBar(ft.Text("Subject connected successfully!"))
            page.snack_bar.open = True
            page.update()

        threading.Thread(target=fetch_cloud_data, daemon=True).start()

    main_screen.content = ft.Column(
        expand=True, spacing=0,
        controls=[
            ft.Container(padding=ft.padding.symmetric(horizontal=20, vertical=15), content=ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                ft.Row([ft.IconButton(ft.icons.MENU, on_click=go_settings), ft.Text("EduNex", size=24, weight="w900", color=ft.colors.PRIMARY), current_subject_text]), 
                ft.Row([theme_btn, ft.TextButton("Clear Chat", on_click=lambda e: chat_history.controls.clear() or page.update())])
            ])),
            ft.Divider(height=1, color=ft.colors.OUTLINE_VARIANT),
            ft.Container(height=60, padding=10, content=ft.Row(scroll="auto", controls=[ft.OutlinedButton(f"Unit {i} Summary", data=f"Unit {i}", on_click=lambda e: action_click(e, "summary"), style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20))) for i in range(1, 6)])),
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

    # --- PROFESSIONAL SETTINGS SCREEN ALIGNMENT ---
    settings_screen.content = ft.Column([
        ft.Container(padding=20, content=ft.Row([ft.IconButton(ft.icons.ARROW_BACK, on_click=go_home), ft.Text("Configuration", size=24, weight="bold")])),
        ft.Container(
            expand=True, alignment=ft.alignment.center,
            content=ft.Card(
                elevation=4,
                content=ft.Container(
                    width=450, padding=40,
                    content=ft.Column(horizontal_alignment=ft.CrossAxisAlignment.CENTER, main_alignment=ft.MainAxisAlignment.CENTER, spacing=20, controls=[
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

    vault_screen.content = ft.Column([ft.Row([ft.IconButton(ft.icons.ARROW_BACK, on_click=go_home), ft.Text("Vault", size=24)]), ft.Divider(), vault_list, vault_viewer])

    page.add(ft.Stack(expand=True, controls=[premium_background, ft.Stack(expand=True, controls=[main_screen, settings_screen, vault_screen, exam_screen])]))

if __name__ == "__main__":
    os.makedirs(EXPORTS_DIR, exist_ok=True)
    os.makedirs(NOTES_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.environ["FLET_SECRET_KEY"] = "EduNex_Secure_Key_2026"
    port = int(os.getenv("PORT", 8550))
    print(f"🌍 Starting EduNex Enterprise on port {port}...")
    ft.app(target=main, view="web_browser", port=port, host="0.0.0.0", assets_dir=ASSETS_DIR, upload_dir=UPLOADS_DIR)

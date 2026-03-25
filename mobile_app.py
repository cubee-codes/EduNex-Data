import flet as ft
import requests
import json
import datetime
import re
import os
import base64
import random 
from collections import Counter
import urllib.parse 
from dotenv import load_dotenv

# ---------------------------------------------------------
# 1. SECURE CONFIGURATION (GITHUB MODELS API)
# ---------------------------------------------------------
load_dotenv() 

API_KEY = os.getenv("GITHUB_API_KEY") 
MODEL_NAME = "gpt-4o-mini" 

CLOUD_DATA = {
    "Operating Systems": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/OS/os.txt", 
        "img_base_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/main/semister5/OS/images", 
        "github_api_url": "https://api.github.com/repos/cubee-codes/EduNex-Data/contents/semister5/OS/images",
        "available_images": [] 
    },
    "Software Testing (SFT)": {
        "txt_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/refs/heads/main/semister5/SFT/sft.txt", 
        "img_base_url": "https://raw.githubusercontent.com/cubee-codes/EduNex-Data/main/semister5/SFT/images", 
        "github_api_url": "https://api.github.com/repos/cubee-codes/EduNex-Data/contents/semister5/SFT/images",
        "available_images": [] 
    }
}

# ---------------------------------------------------------
# 2. ULTRA-FAST SYLLABUS RAG ENGINE
# ---------------------------------------------------------
def fast_search_syllabus(query, chunks, top_k=5, randomize_if_empty=False):
    print("DEBUG: 🧠 Running High-Speed RAG Engine on RAM chunks...")
    if not chunks: 
        return "No syllabus context available."
        
    query_words = set(re.findall(r'\w+', query.lower()))
    
    if not query_words or randomize_if_empty: 
        sampled_chunks = random.sample(chunks, min(top_k, len(chunks)))
        print(f"DEBUG: 🎲 Selected {len(sampled_chunks)} random chunks for Quiz/Viva.")
        return "\n\n--- RANDOM SYLLABUS EXCERPTS ---\n" + "\n...\n".join(sampled_chunks) + "\n----------------------------------\n"

    chunk_scores = []
    for chunk in chunks:
        chunk_lower = chunk.lower()
        score = sum(1 for q in query_words if q in chunk_lower)
        chunk_scores.append((score, chunk))
        
    chunk_scores.sort(key=lambda x: x[0], reverse=True)
    best_chunks = [c[1] for c in chunk_scores[:top_k] if c[0] > 0]
    
    if best_chunks:
        print(f"DEBUG: ✅ Extracted {len(best_chunks)} relevant chunks instantly!")
        return "\n\n--- RELEVANT SYLLABUS EXCERPTS ---\n" + "\n...\n".join(best_chunks) + "\n----------------------------------\n"
    else:
        print("DEBUG: ⚠️ No direct matches. Defaulting to top of syllabus.")
        return "\n\n".join(chunks[:top_k])

# ---------------------------------------------------------
# 3. GITHUB MODELS API TRANSLATION LAYER
# ---------------------------------------------------------
def get_ai_response(user_input, is_exam_mode, chat_history_list, session_files, cached_syllabus_chunks, current_subject_key, is_quiz_mode=False, is_summary_mode=False, is_viva_mode=False, attached_file_path=None):
    if not API_KEY:
        return "❌ CRITICAL ERROR: GITHUB_API_KEY missing. Please check your .env file."
        
    print(f"DEBUG: 🌐 Connecting to GitHub Models API ({MODEL_NAME})...")
    url = "https://models.inference.ai.azure.com/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    if attached_file_path and os.path.exists(attached_file_path):
        if len(session_files) >= 3:
            session_files.pop(0)

        ext = attached_file_path.lower().split('.')[-1]
        original_filename = os.path.basename(attached_file_path)
        filename = original_filename
        
        existing_names = [f["filename"] for f in session_files]
        counter = 1
        while filename in existing_names:
            name, ext_part = os.path.splitext(original_filename)
            filename = f"{name}_{counter}{ext_part}"
            counter += 1

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
        image_instruction = (
            f"\n\n--- LOCAL DIAGRAMS AVAILABLE: {available_images} ---\n"
            "CRITICAL INSTRUCTIONS FOR DIAGRAMS:\n"
            "1. You MUST use these images when explaining topics related to them.\n"
            "2. DO NOT DESCRIBE THE IMAGE'S VISUAL ELEMENTS IN TEXT.\n"
            "3. INSTEAD, ONLY output this EXACT tag: [IMG: filename.png]\n"
            "----------------------------------\n"
        )

    system_prompt = f"You are EduNex, an expert academic AI tutor.\n\nCONTEXT (Syllabus):\n{syllabus_context}"
    
    user_text_string = ""
    has_image = False
    image_list = []

    for f_obj in session_files:
        user_text_string += f"\n\n--- UPLOADED REFERENCE FILE: {f_obj['filename']} ---\n"
        if f_obj["type"] == "text": 
            user_text_string += f"{f_obj['content'][:4000]}\n"
        elif f_obj["type"] == "binary" and f_obj["inline_data"]["mime_type"].startswith("image/"):
            has_image = True
            image_list.append({
                "type": "image_url",
                "image_url": {"url": f"data:{f_obj['inline_data']['mime_type']};base64,{f_obj['inline_data']['data']}"}
            })

    concise_rule = "CRITICAL: Be extremely concise and highly formatted. DO NOT use LaTeX (like a/b). Use standard plain text math and standard markdown ONLY."

    if is_quiz_mode:
        user_text_string += f"\n\nTASK: Generate 10 varied, unrepeated MCQs based strictly on the provided context chunks or uploaded files. Use **Bold** for Question Text. Add an Answer Key. {concise_rule}"
    elif is_viva_mode:
        user_text_string += f"\n\nTASK: Generate 15 unique, rapid-fire oral Viva questions based strictly on the provided context chunks or uploaded files. Format strictly as 'Q: [Question]' followed by 'A: [One-line Answer]'. {concise_rule}"
    elif is_summary_mode:
        user_text_string += f"\n\nTASK: Create a 'One-Page Cheat Sheet' for: {user_input}\n{image_instruction}\n{concise_rule}"
    else:
        style = "⚠️ EXAM MODE: Bullet points, keywords." if is_exam_mode else "🎓 TUTOR MODE: Analogies, deep explanation."
        user_text_string += f"\n\n{history_context}INSTRUCTION: {style}\n{image_instruction}\n{concise_rule}\nCRITICAL RULE: Prioritize the UPLOADED REFERENCE FILE if provided.\nUSER INPUT: {user_input}"

    if has_image:
        user_message_content = [{"type": "text", "text": user_text_string}] + image_list
    else:
        user_message_content = user_text_string

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message_content}
        ],
        "temperature": 0.7 
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=(5.0, 25.0))
        
        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                print("DEBUG: ✅ API generation successful.")
                return result['choices'][0]['message']['content']
            return "Safety Block (No content generated)."
        elif response.status_code == 429:
            print("DEBUG: ⚠️ Error 429 - Rate Limit.")
            return "⚠️ **API Quota Exceeded:** You have reached the API rate limit. Please wait a minute before trying again."
        else:
            print(f"DEBUG: ❌ API Error {response.status_code}: {response.text}")
            return f"❌ API Error {response.status_code}: Unable to process request."
            
    except requests.exceptions.Timeout:
        print("DEBUG: ❌ Request Timed Out.")
        return "❌ **Network Timeout:** The AI took too long to respond. The connection was dropped to prevent freezing."
    except Exception as e:
        print(f"DEBUG: ❌ Exception: {str(e)}")
        return f"❌ Connection Error: {str(e)}"

# ---------------------------------------------------------
# 4. THE APP UI
# ---------------------------------------------------------
def main(page: ft.Page):
    page.title = "EduNex Premium"
    page.bgcolor = "transparent" 
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0

    user_state = {
        "chat_history": [],
        "session_files": [],
        "current_subject": None,
        "cached_syllabus_chunks": []
    }
    
    main_screen = ft.Container(expand=True, visible=True)
    settings_screen = ft.Container(expand=True, visible=False, padding=20)
    vault_screen = ft.Container(expand=True, visible=False, padding=20)

    chat_history = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=15)
    current_subject_text = ft.Text("No Subject Selected", size=12, color="grey", italic=True)

    feedback_text = ft.Text("", size=12, weight="bold", color="#00ff88")
    status_row = ft.Row(controls=[feedback_text], alignment=ft.MainAxisAlignment.CENTER)
    
    search_box = ft.TextField(label="Type to search subject...", bgcolor="#2b2b2b", color="white", border_radius=10, text_size=14)
    unified_dropdown = ft.Dropdown(label="Select from list", bgcolor="#2b2b2b", color="white", border_color="#444", border_radius=10, options=[ft.dropdown.Option(key) for key in CLOUD_DATA.keys()], width=300)
    mode_switch = ft.Switch(label="Exam Mode (Strict)", active_color="#ff4444", inactive_thumb_color="#00ff88", value=False)

    vault_list = ft.ListView(expand=True, spacing=10)
    vault_viewer = ft.Column(expand=True, scroll="always", visible=False)

    chat_box = ft.TextField(
        hint_text="Ask a question... (Press Enter to Send)", 
        hint_style=ft.TextStyle(color="#888888"),
        bgcolor="#1Affffff", 
        color="white", 
        border_radius=25, 
        border_color="#33ffffff", 
        content_padding=15, 
        expand=True
    )
    
    send_button = ft.ElevatedButton(
        content=ft.Text("➤", color="black", size=18, weight="bold"), 
        style=ft.ButtonStyle(bgcolor="#00ff88", shape=ft.CircleBorder(), padding=15)
    )

    def show_feedback(message, color="#00ff88"):
        feedback_text.value = message
        feedback_text.color = color
        page.update()
        
        def clear_text():
            import time
            time.sleep(3.5)
            if feedback_text.value == message: 
                feedback_text.value = ""
                page.update()
                
        import threading
        threading.Thread(target=clear_text, daemon=True).start()

    def go_settings(e):
        search_box.value = ""
        main_screen.visible, settings_screen.visible, vault_screen.visible = False, True, False
        page.update()

    def go_home(e):
        main_screen.visible, settings_screen.visible, vault_screen.visible = True, False, False
        page.update()
    
    def add_message(text, is_user=False, is_quiz=False, is_summary=False, is_viva=False):
        sender = "You" if is_user else "EduNex"
        timestamp = datetime.datetime.now().strftime("%H:%M")
        
        user_state["chat_history"].append(f"[{timestamp}] {sender}:\n{text}\n" + "-"*40 + "\n")
        
        if len(user_state["chat_history"]) > 10:
            user_state["chat_history"].pop(0)
            show_feedback("🧹 AI Memory optimized (Oldest exchange cleared)", color="#ff8800")
        
        bg_color = "#CC2b2b2b" if is_user else "#CC111111" 
        if not is_user:
            if "Error" in text or "❌" in text or "Timeout" in text or "Quota" in text or "⚠️" in text: 
                bg_color = "#CC330000"
            elif is_quiz: 
                bg_color = "#CC1a1a00"
            elif is_summary: 
                bg_color = "#CC001a1a"
            elif is_viva: 
                bg_color = "#CC1a0d00" 
            elif mode_switch.value: 
                bg_color = "#CC1a0000"

        message_elements = []
        if is_user:
            message_elements.append(ft.Text(text, color="white", size=15))
        else:
            parts = re.split(r'\[IMG:(.*?)\]', text)
            for i, part in enumerate(parts):
                part = part.strip()
                if not part: continue
                if i % 2 == 0:
                    message_elements.append(ft.Markdown(part, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=15, color="#e0e0e0"))))
                else:
                    curr_subj = user_state["current_subject"]
                    if curr_subj and curr_subj in CLOUD_DATA:
                        base_img_url = CLOUD_DATA[curr_subj]["img_base_url"]
                        safe_filename = urllib.parse.quote(part)
                        final_img_url = f"{base_img_url}/{safe_filename}"
                        message_elements.append(ft.Row(controls=[ft.Image(src=final_img_url, width=350, border_radius=10)], alignment=ft.MainAxisAlignment.CENTER))

        bubble = ft.Container(content=ft.Column(controls=message_elements, spacing=10), bgcolor=bg_color, padding=15, border_radius=10, expand=True)
        chat_row = ft.Row(controls=[ft.Container(width=50), bubble] if is_user else [bubble, ft.Container(width=50)], vertical_alignment=ft.CrossAxisAlignment.START)
        chat_history.controls.append(ft.Container(content=chat_row, padding=5)) 

        chat_history.update()
        page.update()

    def execute_ai_task(msg, is_quiz=False, is_summary=False, is_viva=False):
        chat_box.disabled = True
        send_button.disabled = True
        
        loading_bubble = ft.Container(
            content=ft.Row([
                ft.ProgressRing(width=16, height=16, color="#00ff88", stroke_width=2),
                ft.Text(" AI is analyzing...", color="#00ff88", italic=True, weight="bold")
            ]), 
            padding=15, bgcolor="#111111", border_radius=10
        )
        chat_history.controls.append(loading_bubble)
        page.update()
        
        def background_worker():
            try:
                resp = get_ai_response(
                    user_input=msg, is_exam_mode=mode_switch.value, chat_history_list=user_state["chat_history"], 
                    session_files=user_state["session_files"], cached_syllabus_chunks=user_state["cached_syllabus_chunks"], 
                    current_subject_key=user_state["current_subject"], is_quiz_mode=is_quiz, is_summary_mode=is_summary, 
                    is_viva_mode=is_viva, attached_file_path=None
                )
                if loading_bubble in chat_history.controls:
                    chat_history.controls.remove(loading_bubble)
                add_message(str(resp), is_quiz=is_quiz, is_summary=is_summary, is_viva=is_viva)
            except Exception as e:
                if loading_bubble in chat_history.controls:
                    chat_history.controls.remove(loading_bubble)
                add_message(f"❌ System Fault: {str(e)}")
            finally:
                chat_box.disabled = False
                send_button.disabled = False
                page.update()

        import threading
        threading.Thread(target=background_worker, daemon=True).start()

    def is_subject_loaded():
        if not user_state["current_subject"]:
            show_feedback("⚠️ Please select a subject from Configuration first!", color="#ff4444")
            return False
        return True

    def send_click(e):
        if chat_box.disabled: 
            return 
        if not chat_box.value: 
            return
            
        msg = chat_box.value
        chat_box.value = ""
        page.update()
        
        add_message(msg, is_user=True)
        execute_ai_task(msg)

    chat_box.on_submit = send_click
    send_button.on_click = send_click

    def summary_click(e):
        if not is_subject_loaded(): return
        topic = e.control.data
        add_message(f"Cheat Sheet: {topic}", is_user=True)
        execute_ai_task(topic, is_summary=True)

    def quiz_click(e):
        if not is_subject_loaded(): return
        add_message("Quiz Me!", is_user=True)
        execute_ai_task("", is_quiz=True)

    def viva_click(e):
        if not is_subject_loaded(): return
        add_message("Prep me for Viva!", is_user=True)
        execute_ai_task("", is_viva=True)

    def bookmark_click(e):
        hist = user_state["chat_history"]
        last_ai_msg = next((msg for msg in reversed(hist) if "EduNex:\n" in msg), None)
        
        if not last_ai_msg: 
            show_feedback("⚠️ Chat is empty! Nothing to bookmark.", color="#ff4444")
            return
            
        os.makedirs("saved_notes", exist_ok=True)
        try:
            with open("saved_notes/Revision_List.txt", "a", encoding="utf-8") as f:
                f.write(f"\n--- ⭐ Bookmarked on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ---\nSubject: {user_state['current_subject']}\n{last_ai_msg}\n")
            show_feedback("⭐ Saved to Revision Vault!", color="#ffd700")
        except Exception: 
            pass

    def export_click(e):
        hist = user_state["chat_history"]
        last_ai_msg = next((msg for msg in reversed(hist) if "EduNex:\n" in msg), None)
        
        if not last_ai_msg: 
            show_feedback("⚠️ Chat is empty! Nothing to export.", color="#ff4444")
            return
            
        last_ai_msg = re.sub(r'\[.*?\] EduNex:\n', '', last_ai_msg).replace("-" * 40 + "\n", "").strip()
        last_ai_msg = re.sub(r'\[IMG:.*?\]', '[Diagram available in EduNex App]', last_ai_msg)
        
        clean_text = last_ai_msg.encode('ascii', 'ignore').decode('ascii')
        
        os.makedirs("assets/exports", exist_ok=True)
        filename = f"EduNex_Guide_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.pdf"
        filepath = os.path.join("assets/exports", filename)
        
        try:
            from fpdf import FPDF
            class PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 15)
                    self.cell(0, 10, 'EduNex AI Study Guide', 0, 1, 'C')
                    self.set_font('Arial', 'I', 10)
                    self.cell(0, 10, f"Subject: {user_state['current_subject']}", 0, 1, 'C')
                    self.ln(10)
                def footer(self):
                    self.set_y(-15)
                    self.set_font('Arial', 'I', 8)
                    self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')
            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=11)
            pdf.multi_cell(0, 7, clean_text)
            pdf.output(filepath)
            
            show_feedback("📄 PDF generated! Downloading...", color="#00ff88")
            page.launch_url(f"/exports/{filename}")
            
        except Exception: 
            show_feedback("❌ Failed to generate PDF.", color="#ff4444")

    def clear_chat_click(e):
        chat_history.controls.clear()
        user_state["chat_history"] = []
        user_state["session_files"] = [] 
        
        show_feedback("🗑️ Chat Memory Cleared!", color="#ff4444")
        page.update()

    def on_search_change(e):
        search_term = search_box.value.lower() if search_box.value else ""
        filtered_options = [
            ft.dropdown.Option(key) for key in CLOUD_DATA.keys() 
            if search_term in key.lower()
        ]
        unified_dropdown.options = filtered_options
        current_valid_keys = [opt.key for opt in filtered_options]
        if unified_dropdown.value not in current_valid_keys:
            unified_dropdown.value = None
        unified_dropdown.update()
        
    search_box.on_change = on_search_change
    mode_switch.on_change = lambda e: (setattr(mode_switch, 'label', "Exam Mode (Strict)" if mode_switch.value else "Tutor Mode (Friendly)"), mode_switch.update())

    def apply_settings_click(e):
        selected_name = unified_dropdown.value
        if not selected_name: return

        user_state["current_subject"] = selected_name
        current_subject_text.value = f"Connecting to {selected_name}..."
        current_subject_text.color = "#00ff88"
        
        go_home(None)
        
        def fetch_cloud_data():
            if CLOUD_DATA[selected_name].get("txt_url"):
                try:
                    current_subject_text.value = f"Caching Syllabus into RAM..."
                    page.update()
                    resp_txt = requests.get(CLOUD_DATA[selected_name]["txt_url"], timeout=5)
                    
                    if resp_txt.status_code == 200: 
                        raw_text = resp_txt.text
                        chunk_size = 1500
                        chunks = [raw_text[i:i+chunk_size] for i in range(0, len(raw_text), chunk_size)]
                        user_state["cached_syllabus_chunks"] = chunks
                    else:
                        show_feedback(f"❌ Cloud Error: HTTP {resp_txt.status_code}", color="#ff4444")
                        current_subject_text.value = "No Subject Selected"
                        page.update()
                        return
                        
                except Exception: 
                    show_feedback("❌ Network Error: Failed to fetch Cloud Syllabus.", color="#ff4444")
                    current_subject_text.value = "No Subject Selected"
                    page.update()
                    return
                    
            if CLOUD_DATA[selected_name].get("github_api_url") and not CLOUD_DATA[selected_name]["available_images"]:
                try:
                    resp = requests.get(CLOUD_DATA[selected_name]["github_api_url"], timeout=5)
                    if resp.status_code == 200: 
                        CLOUD_DATA[selected_name]["available_images"] = [f["name"] for f in resp.json() if f["name"].lower().endswith(('.png', '.jpg', '.jpeg'))]
                except Exception: pass
                    
            current_subject_text.value = f"Selected: {selected_name} ☁️"
            clear_chat_click(None)
            show_feedback("✅ Applied Settings! Connected to Cloud.", color="#00ff88")
            page.update()

        import threading
        threading.Thread(target=fetch_cloud_data, daemon=True).start()

    def load_vault_files(e):
        vault_list.controls.clear()
        vault_viewer.visible = False
        vault_list.visible = True
        has_files = False
        for folder in ["saved_notes", "assets/exports"]:
            if os.path.exists(folder):
                for filename in os.listdir(folder):
                    if filename.endswith((".txt", ".md", ".pdf")):
                        has_files = True
                        file_path = os.path.join(folder, filename)
                        vault_list.controls.append(ft.ElevatedButton(content=ft.Text(f"📄 {filename}", color="white"), style=ft.ButtonStyle(bgcolor="#222222", shape=ft.RoundedRectangleBorder(radius=10), padding=20), width=350, on_click=lambda e, fp=file_path: open_vault_file(fp)))
        
        if not has_files: 
            vault_list.controls.append(ft.Text("No saved notes found yet!", color="grey", italic=True))
            
        main_screen.visible, settings_screen.visible, vault_screen.visible = False, False, True
        page.update()
        
    def open_vault_file(filepath):
        if filepath.endswith(".pdf"):
            filename = os.path.basename(filepath)
            page.launch_url(f"/exports/{filename}")
        else:
            try:
                with open(filepath, "r", encoding="utf-8") as f: content = f.read()
                vault_viewer.controls.clear()
                vault_viewer.controls.append(ft.ElevatedButton(content=ft.Text("← Close File", color="#ff4444"), style=ft.ButtonStyle(bgcolor="#222222"), on_click=lambda e: (setattr(vault_viewer, 'visible', False), setattr(vault_list, 'visible', True), page.update())))
                vault_viewer.controls.append(ft.Divider(color="#333333"))
                vault_viewer.controls.append(ft.Markdown(content, extension_set=ft.MarkdownExtensionSet.GITHUB_WEB, md_style_sheet=ft.MarkdownStyleSheet(p_text_style=ft.TextStyle(size=14, color="white"))))
                vault_list.visible, vault_viewer.visible = False, True
                page.update()
            except Exception: pass

    main_screen.content = ft.Column(
        expand=True, spacing=0,
        controls=[
            ft.Container(
                padding=10, 
                content=ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(controls=[ft.ElevatedButton(content=ft.Text("☰", size=24, color="#00ff88"), style=ft.ButtonStyle(bgcolor="#111111", shape=ft.CircleBorder(), padding=5), on_click=go_settings), ft.Text("EduNex", size=20, weight="bold", color="#00ff88")]), 
                        ft.Row(controls=[ft.ElevatedButton(content=ft.Text("📁 Vault", size=12, color="#00e5ff"), style=ft.ButtonStyle(bgcolor="#111111", shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, "#00e5ff"), padding=10), on_click=load_vault_files), ft.ElevatedButton(content=ft.Text("📄 PDF", size=12, color="#00ff88"), style=ft.ButtonStyle(bgcolor="#111111", shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, "#00ff88"), padding=10), on_click=export_click), ft.ElevatedButton(content=ft.Text("Clear", size=12, color="#ff4444"), style=ft.ButtonStyle(bgcolor="#111111", shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, "#ff4444"), padding=10), on_click=clear_chat_click)])
                    ]
                )
            ),
            ft.Container(content=current_subject_text, padding=10),
            
            ft.Container(content=status_row, alignment=ft.Alignment(0, 0), height=20),
            
            ft.Container(height=45, padding=10, content=ft.Row(scroll="always", controls=[ft.ElevatedButton(content=ft.Text(f"Unit {i}", color="#00e5ff", size=12), data=f"Unit {i}", on_click=summary_click, style=ft.ButtonStyle(bgcolor="#CC222222", shape=ft.RoundedRectangleBorder(radius=20))) for i in range(1, 6)])),
            ft.Divider(color="#333333", height=1),
            ft.Container(content=chat_history, expand=True), 
            
            ft.Container(
                padding=15, bgcolor="#33000000", blur=30, border=ft.border.only(top=ft.border.BorderSide(1, "#22ffffff")), border_radius=ft.border_radius.only(top_left=25, top_right=25),
                content=ft.Column(
                    controls=[
                        ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_EVENLY, wrap=True,
                            controls=[
                                ft.ElevatedButton(content=ft.Text("🎯 Quiz", color="#ffd700", weight="bold"), style=ft.ButtonStyle(bgcolor="#CC1a1a00", side=ft.BorderSide(1, "#ffd700"), shape=ft.RoundedRectangleBorder(radius=20)), on_click=quiz_click),
                                ft.ElevatedButton(content=ft.Text("🗣️ Viva", color="#00e5ff", weight="bold"), style=ft.ButtonStyle(bgcolor="#CC001a1a", side=ft.BorderSide(1, "#00e5ff"), shape=ft.RoundedRectangleBorder(radius=20)), on_click=viva_click),
                                ft.ElevatedButton(content=ft.Text("⭐ Mark", color="#ff8800", weight="bold"), style=ft.ButtonStyle(bgcolor="#CC1a0a00", side=ft.BorderSide(1, "#ff8800"), shape=ft.RoundedRectangleBorder(radius=20)), on_click=bookmark_click)
                            ]
                        ), 
                        ft.Row(
                            controls=[
                                chat_box, ft.Container(width=5), send_button
                            ]
                        )
                    ]
                ) 
            )
        ]
    )

    settings_screen.content = ft.Column(
        controls=[
            ft.Container(height=20),
            ft.Row(controls=[ft.ElevatedButton(content=ft.Text("← Back", color="white"), style=ft.ButtonStyle(bgcolor="#333333"), on_click=go_home), ft.Text("Configuration", size=22, weight="bold")]),
            ft.Divider(color="grey"),
            ft.Container(
                expand=True, 
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.START, scroll="always",
                    controls=[
                        ft.Text("🔎 Find Subject", color="#00ff88", weight="bold", size=16), ft.Container(height=10), search_box, ft.Container(height=5), unified_dropdown, ft.Container(height=30),
                        ft.Text("🧠 AI Personality", color="#00ff88", weight="bold", size=16), ft.Container(height=10), ft.Container(content=mode_switch, bgcolor="#222222", padding=15, border_radius=15, width=300, alignment=ft.Alignment(0, 0)), ft.Container(height=30),
                        ft.ElevatedButton(content=ft.Text("APPLY CHANGES", size=14, weight="bold", color="black"), style=ft.ButtonStyle(bgcolor="#00ff88", shape=ft.RoundedRectangleBorder(radius=10)), width=300, height=50, on_click=apply_settings_click)
                    ]
                )
            ),
        ]
    )

    vault_screen.content = ft.Column(
        controls=[
            ft.Container(height=20),
            ft.Row(controls=[ft.ElevatedButton(content=ft.Text("← Back", color="white"), style=ft.ButtonStyle(bgcolor="#333333"), on_click=go_home), ft.Text("Study Vault", size=22, weight="bold", color="#00e5ff")]),
            ft.Divider(color="grey"),
            vault_list, vault_viewer
        ]
    )

    premium_background = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment(-1, -1), 
            end=ft.Alignment(1, 1),     
            colors=["#0B0B13", "#1A1525", "#0F172A"], 
        )
    )

    page.add(
        ft.Stack(
            expand=True,
            controls=[
                premium_background, 
                ft.Stack(expand=True, controls=[main_screen, settings_screen, vault_screen])
            ]
        )
    )

# ---------------------------------------------------------
# 5. APP LAUNCHER (RENDER-READY ENGINE)
# ---------------------------------------------------------
if __name__ == "__main__":
    os.makedirs("assets/exports", exist_ok=True)
    
    port = int(os.getenv("PORT", 8550))
    
    print(f"🌍 Starting EduNex Web Server on port {port}...")
    
    ft.app(
        target=main, 
        view="web_browser", 
        port=port, 
        host="0.0.0.0", 
        assets_dir="assets"
    )

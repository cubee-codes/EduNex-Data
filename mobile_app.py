import flet as ft
import requests
import json
import os
import datetime

# ---------------------------------------------------------
# 1. CONFIGURATION
# ---------------------------------------------------------
API_KEY = "AIzaSyAnStc-aQpMnKiwlSw3NAh0cAyIds1u-0g"
MODEL_NAME = "gemini-2.5-flash"

# Global State
current_full_path = ""
current_display_name = "No Subject Selected"
session_data = [] 
ALL_SUBJECTS = {} 

def load_subjects_from_disk():
    global ALL_SUBJECTS
    ALL_SUBJECTS = {}
    base_folder = "data"
    
    if not os.path.exists(base_folder):
        os.makedirs(base_folder)
        return

    for root, dirs, files in os.walk(base_folder):
        for file in files:
            if file.endswith(".txt"):
                folder_name = os.path.basename(root)
                file_name = os.path.splitext(file)[0]
                display_name = f"{file_name} ({folder_name})"
                full_path = os.path.join(root, file)
                ALL_SUBJECTS[display_name] = full_path

def get_ai_response(user_input, is_exam_mode, is_quiz_mode=False, is_summary_mode=False, is_viva_mode=False, chat_history_list=None):
    print(f"DEBUG: Calling AI...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
    headers = {'Content-Type': 'application/json'}
    
    syllabus_text = ""
    if current_full_path and os.path.exists(current_full_path):
        try:
            with open(current_full_path, "r", encoding="utf-8") as f:
                syllabus_text = f.read()[:80000]
        except Exception as e:
            syllabus_text = f"Error reading file: {e}"
    else:
        syllabus_text = "No subject selected. Please select a subject from settings."
        
    history_context = ""
    if chat_history_list and len(chat_history_list) > 0:
        recent_history = "".join(chat_history_list[-6:])
        history_context = f"\n--- RECENT CHAT HISTORY ---\n{recent_history}\n---------------------------\n"
            
    # 🌟 UPDATE: Instant Answer Key with Explanations
    if is_quiz_mode:
        final_prompt = (
            f"CONTEXT (Syllabus): {syllabus_text}\n\n"
            "TASK: Generate 5 Multiple Choice Questions (MCQs) based on the syllabus.\n"
            "STRICT FORMATTING RULES:\n"
            "1. Use **Bold** ONLY for the Question Text.\n"
            "2. Format Options (A, B, C, D) as a BULLET LIST.\n"
            "3. Add '---' separator between questions.\n"
            "4. IMPORTANT: Provide an 'Answer Key' at the very bottom. For each answer, include a brief 1-sentence explanation of why it is correct."
        )
    elif is_viva_mode:
        final_prompt = (
            f"CONTEXT (Syllabus): {syllabus_text}\n\n"
            "TASK: Generate 20 rapid-fire oral Viva questions covering the ENTIRE syllabus evenly.\n"
            "STRICT FORMATTING RULES:\n"
            "1. Format strictly as 'Q: [Question]' followed by 'A: [One-line Answer]'.\n"
            "2. Keep the answers very brief and factual.\n"
            "3. Ensure topics from every single unit/chapter are included."
        )
    elif is_summary_mode:
        final_prompt = (
            f"CONTEXT (Syllabus): {syllabus_text}\n\n"
            f"TASK: Create a 'One-Page Cheat Sheet' for: {user_input}\n"
            "FORMAT: Key Definitions, Formulas, Top 3 Exam Questions."
        )
    else:
        style = "⚠️ EXAM MODE: Bullet points, keywords." if is_exam_mode else "🎓 TUTOR MODE: Analogies, deep explanation."
        final_prompt = (
            f"CONTEXT (Syllabus): {syllabus_text}\n"
            f"{history_context}"
            f"INSTRUCTION: {style}\n"
            f"USER INPUT: {user_input}"
        )

    try:
        data = {"contents": [{"parts": [{"text": final_prompt}]}]}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            result = response.json()
            if 'candidates' in result:
                return result['candidates'][0]['content']['parts'][0]['text']
            return "Safety Block (No content)."
        return f"Error {response.status_code}: {response.text}"
    except Exception as e:
        return f"Connection Error: {e}"

# ---------------------------------------------------------
# 2. THE APP UI
# ---------------------------------------------------------
def main(page: ft.Page):
    load_subjects_from_disk()
    
    page.title = "EduNex Mobile"
    page.window_width = 390
    page.window_height = 844
    page.bgcolor = "#0a0a0a" 
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 0
    
    # --- SHARED UI COMPONENTS ---
    chat_history = ft.ListView(expand=True, spacing=15, auto_scroll=True, padding=10)
    feedback_text = ft.Text("", size=12, weight="bold", color="#00ff88")
    current_subject_text = ft.Text("No Subject Selected", size=12, color="grey", italic=True)

    chat_box = ft.TextField(
        hint_text="Ask a question...", 
        hint_style=ft.TextStyle(color="#555555"),
        bgcolor="#1f1f1f", color="white", 
        border_radius=25, border_color="#333333", 
        content_padding=ft.padding.only(left=20, right=20, top=15, bottom=15),
        expand=True
    )
    
    # --- FUNCTIONS ---
    def add_message(text, is_user=False, is_quiz=False, is_summary=False, is_viva=False):
        sender = "You" if is_user else "AI"
        timestamp = datetime.datetime.now().strftime("%H:%M")
        session_data.append(f"[{timestamp}] {sender}:\n{text}\n" + "-"*40 + "\n")
        
        bg_color = "#2b2b2b" if is_user else "#111111"
        if not is_user:
            if "Error 429" in text: bg_color = "#330000"
            elif is_quiz: bg_color = "#1a1a00"
            elif is_summary: bg_color = "#001a1a"
            elif is_viva: bg_color = "#1a0d00" 
            elif mode_switch.value: bg_color = "#1a0000"

        content_control = ft.Text(text, color="white", size=15) if is_user else ft.Markdown(
            text, 
            extension_set=ft.MarkdownExtensionSet.GITHUB_WEB,
            md_style_sheet=ft.MarkdownStyleSheet(
                p_text_style=ft.TextStyle(size=15, color="#e0e0e0", font_family="Roboto"), 
                strong_text_style=ft.TextStyle(size=16, weight="bold", color="white")
            )
        )

        chat_history.controls.append(
            ft.Container(
                content=content_control,
                bgcolor=bg_color,
                padding=15,
                border_radius=10,
                margin=ft.margin.only(
                    left=50 if is_user else 0, 
                    right=0 if is_user else 50,
                    bottom=5
                )
            )
        )
        page.update()

    def send_click(e):
        if not chat_box.value: return
        msg = chat_box.value
        chat_box.value = ""
        add_message(msg, is_user=True)
        feedback_text.value = "Thinking..."
        page.update()
        
        resp = get_ai_response(msg, is_exam_mode=mode_switch.value, chat_history_list=session_data)
        
        add_message(resp)
        feedback_text.value = ""
        page.update()
    
    chat_box.on_submit = send_click

    def summary_click(e):
        topic = e.control.data
        add_message(f"Cheat Sheet: {topic}", is_user=True)
        feedback_text.value = "Summarizing..."
        page.update()
        resp = get_ai_response(topic, is_exam_mode=mode_switch.value, is_summary_mode=True)
        add_message(resp, is_summary=True)
        feedback_text.value = ""
        page.update()

    def quiz_click(e):
        add_message("Quiz Me!", is_user=True)
        feedback_text.value = "Generating Quiz & Answer Key..."
        page.update()
        resp = get_ai_response("", is_exam_mode=mode_switch.value, is_quiz_mode=True)
        add_message(resp, is_quiz=True)
        feedback_text.value = ""
        page.update()

    def viva_click(e):
        add_message("Prep me for Viva!", is_user=True)
        feedback_text.value = "Generating 20 Viva Questions..."
        page.update()
        resp = get_ai_response("", is_exam_mode=mode_switch.value, is_viva_mode=True)
        add_message(resp, is_viva=True)
        feedback_text.value = ""
        page.update()

    def bookmark_click(e):
        if not session_data: 
            feedback_text.value = "⚠️ Nothing to bookmark!"
            page.update()
            return

        last_ai_msg = None
        for msg in reversed(session_data):
            if "AI:\n" in msg:
                last_ai_msg = msg
                break
        
        if not last_ai_msg:
            feedback_text.value = "⚠️ No AI response to bookmark!"
            page.update()
            return
            
        folder = "saved_notes"
        if not os.path.exists(folder): os.makedirs(folder)
            
        filepath = os.path.join(folder, "Revision_List.txt")
        
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(f"\n--- ⭐ Bookmarked on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} ---\n")
                f.write(f"Subject: {current_display_name}\n")
                f.write(last_ai_msg)
                f.write("\n")
            feedback_text.value = "⭐ Saved to Revision_List.txt!"
        except Exception as ex:
            feedback_text.value = f"❌ Error: {ex}"
        page.update()

    def save_chat_click(e):
        if not session_data: 
            feedback_text.value = "⚠️ Nothing to save!"
            page.update()
            return

        folder = "saved_notes"
        if not os.path.exists(folder): os.makedirs(folder)
            
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"Chat_{timestamp}.txt"
        filepath = os.path.join(folder, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(f"Subject: {current_display_name}\n\n")
                for line in session_data:
                    f.write(line)
            feedback_text.value = f"✅ Saved: {filename}"
        except Exception as ex:
            feedback_text.value = f"❌ Error: {ex}"
        page.update()

    def clear_chat_click(e):
        chat_history.controls.clear()
        session_data.clear()
        feedback_text.value = "🗑️ Chat Cleared"
        page.update()

    # --- SETTINGS UI ---
    search_box = ft.TextField(
        label="Type to search subject...", 
        hint_text="e.g. 'math' or 'sem 1'",
        bgcolor="#2b2b2b", color="white", border_radius=10, text_size=14
    )
    
    unified_dropdown = ft.Dropdown(
        label="Select from list", bgcolor="#2b2b2b", color="white", border_color="#444", border_radius=10,
        options=[], width=300
    )
    
    mode_switch = ft.Switch(label="Exam Mode (Strict)", active_color="#ff4444", inactive_thumb_color="#00ff88", value=False)

    def update_dropdown_options(search_query=""):
        unified_dropdown.options = []
        sorted_names = sorted(ALL_SUBJECTS.keys())
        for name in sorted_names:
            if not search_query or search_query.lower() in name.lower():
                unified_dropdown.options.append(ft.dropdown.Option(name))
        unified_dropdown.update()

    def on_search_change(e):
        update_dropdown_options(search_box.value)

    search_box.on_change = on_search_change
    
    def on_mode_change(e):
        if mode_switch.value:
            mode_switch.label = "Exam Mode (Strict)"
            mode_switch.active_color = "#ff4444"
        else:
            mode_switch.label = "Tutor Mode (Friendly)"
        mode_switch.update()
    
    mode_switch.on_change = on_mode_change

    def apply_settings_click(e):
        global current_full_path, current_display_name
        selected_name = unified_dropdown.value
        
        if selected_name:
            current_display_name = selected_name
            current_full_path = ALL_SUBJECTS[selected_name]
            
            current_subject_text.value = f"Selected: {current_display_name}"
            current_subject_text.color = "#00ff88"
            current_subject_text.update()
            
            chat_history.controls.clear()
            session_data.clear() 
            add_message(f"✅ Applied Settings!\nActive Subject: **{selected_name}**")
            go_home(None)
        else:
            go_home(None)

    # --- SCREENS ---
    
    # 1. Home Screen
    main_screen = ft.Column(
        expand=True, 
        spacing=0,
        controls=[
            ft.Container(
                padding=ft.padding.only(left=10, right=10, top=10, bottom=5),
                content=ft.Row([
                    ft.Row([
                        ft.ElevatedButton(
                            content=ft.Text("☰", size=24, color="#00ff88"), 
                            bgcolor="#111111", 
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=5),
                            on_click=lambda e: go_settings(e)
                        ),
                        ft.Text("EduNex", size=20, weight="bold", color="#00ff88")
                    ]), 
                    ft.Row([
                        ft.ElevatedButton(
                            content=ft.Text("Save", size=12, color="#00ff88"), 
                            bgcolor="#111111", 
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, "#00ff88"), padding=10),
                            on_click=save_chat_click
                        ),
                        ft.ElevatedButton(
                            content=ft.Text("Clear", size=12, color="#ff4444"), 
                            bgcolor="#111111", 
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8), side=ft.BorderSide(1, "#ff4444"), padding=10),
                            on_click=clear_chat_click
                        )
                    ])
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ),
            ft.Container(content=current_subject_text, padding=ft.padding.only(left=20, bottom=5)),
            ft.Container(content=feedback_text, alignment=ft.Alignment(0, 0), height=20),
            
            ft.Container(
                height=45, 
                padding=ft.padding.only(left=10, bottom=10),
                content=ft.Row(
                    [ft.ElevatedButton(
                        content=ft.Text(f"Unit {i}", color="#00e5ff", size=12), 
                        data=f"Unit {i}", 
                        on_click=summary_click, 
                        bgcolor="#222222",
                        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=20))
                    ) for i in range(1, 6)],
                    scroll="always"
                )
            ),
            ft.Divider(color="#333333", height=1),
            ft.Container(content=chat_history, expand=True, bgcolor="#0a0a0a"),
            
            ft.Container(
                content=ft.Column([
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_EVENLY,
                        wrap=True,
                        controls=[
                            ft.ElevatedButton(
                                content=ft.Text("🎯 Quiz Me", color="#ffd700", weight="bold"), 
                                bgcolor="#1a1a00", 
                                style=ft.ButtonStyle(side=ft.BorderSide(1, "#ffd700"), shape=ft.RoundedRectangleBorder(radius=20)),
                                on_click=quiz_click
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("🗣️ Viva", color="#00e5ff", weight="bold"), 
                                bgcolor="#001a1a", 
                                style=ft.ButtonStyle(side=ft.BorderSide(1, "#00e5ff"), shape=ft.RoundedRectangleBorder(radius=20)),
                                on_click=viva_click
                            ),
                            ft.ElevatedButton(
                                content=ft.Text("⭐ Bookmark", color="#ff8800", weight="bold"), 
                                bgcolor="#1a0a00", 
                                style=ft.ButtonStyle(side=ft.BorderSide(1, "#ff8800"), shape=ft.RoundedRectangleBorder(radius=20)),
                                on_click=bookmark_click
                            )
                        ]
                    ), 
                    ft.Container(height=10),
                    ft.Row([
                        chat_box, 
                        ft.Container(width=5), 
                        ft.ElevatedButton(
                            content=ft.Text("➤", color="black", size=18, weight="bold"), 
                            bgcolor="#00ff88", 
                            style=ft.ButtonStyle(shape=ft.CircleBorder(), padding=15), 
                            on_click=send_click
                        )
                    ])
                ]),
                padding=20, 
                bgcolor="#111111", 
                border_radius=ft.border_radius.only(top_left=25, top_right=25)
            )
        ]
    )

    # 2. Settings Screen
    settings_screen = ft.Container(
        padding=20,
        visible=False,
        expand=True,
        content=ft.Column([
            ft.Container(height=20),
            ft.Row([
                ft.ElevatedButton(
                    content=ft.Text("← Back", color="white"), 
                    bgcolor="#333333", 
                    on_click=lambda e: go_home(e)
                ),
                ft.Text("Configuration", size=22, weight="bold")
            ]),
            ft.Divider(color="grey"),
            
            ft.Container(expand=True, content=ft.Column([
                ft.Text("🔎 Find Subject", color="#00ff88", weight="bold", size=16),
                ft.Container(height=10),
                search_box, 
                ft.Container(height=5),
                unified_dropdown, 
                
                ft.Container(height=50),
                
                ft.Text("🧠 AI Personality", color="#00ff88", weight="bold", size=16),
                ft.Container(height=10),
                ft.Container(
                    content=mode_switch,
                    bgcolor="#222222",
                    padding=15,
                    border_radius=15,
                    width=250,
                    alignment=ft.Alignment(0, 0)
                ),
                
                ft.Container(height=50),
                
                ft.ElevatedButton(
                    content=ft.Text("APPLY CHANGES", size=14, weight="bold", color="black"),
                    bgcolor="#00ff88",
                    width=250,
                    height=50,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
                    on_click=apply_settings_click
                )
                
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER)),
        ])
    )

    def go_settings(e):
        load_subjects_from_disk()
        update_dropdown_options("")
        search_box.value = ""
        main_screen.visible = False
        settings_screen.visible = True
        page.update()

    def go_home(e):
        main_screen.visible = True
        settings_screen.visible = False
        page.update()

    page.add(main_screen, settings_screen)
    update_dropdown_options()

ft.app(target=main)
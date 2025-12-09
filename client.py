import tkinter as tk
from tkinter import ttk, simpledialog, messagebox, scrolledtext, filedialog
import paramiko
import os
import json
import subprocess
import threading
from openai import OpenAI

# Tray support
try:
    import pystray
except ImportError:
    pystray = None

try:
    from PIL import Image, ImageTk, ImageDraw
    HAS_IMAGE_TK = True
except ImportError:
    from PIL import Image, ImageDraw
    HAS_IMAGE_TK = False
    print("Warning: PIL.ImageTk not found. Image previews will be disabled.")
    print("To fix on Fedora: sudo dnf install python3-pillow-tk")

# --- CONFIGURATION ---
HOST = "127.0.0.1"  # Localhost
USER = os.path.expanduser("~").split(os.sep)[-1] or "user"
KEY_PATH = os.path.expanduser("~/.ssh/id_ed25519")

def get_openai_key():
    try:
        key_path = os.path.expanduser("~/keys/openaikey.json")
        with open(key_path, 'r') as f:
            data = json.load(f)
            return data.get("OPENAI_API_KEY")
    except Exception as e:
        print(f"Error loading API key: {e}")
        return None

OPENAI_KEY = get_openai_key()

class RemoteExplorer(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Neural SSH Explorer")
        self.geometry("1200x700")
        self.minsize(900, 600) # Prevent sizing too small
        
        # SSH Client Setup
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.sftp = None
        self.current_path = os.getcwd() # Default to current dir for local mode
        self.use_local_mode = False
        self.fs_context = ""  # Store the file system overview
        
        # Navigation History
        self.history_back = []
        self.history_fwd = []
        self.tray_icon = None
        self.tray_thread = None
        self.tray_running = False
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # OpenAI Client
        if not OPENAI_KEY:
            messagebox.showerror("Error", "Could not load OPENAI_API_KEY from ~/keys/openaikey.json")
            self.destroy()
            return

        self.ai_client = OpenAI(api_key=OPENAI_KEY)

        self.create_gui()
        self.connect_ssh()

    def create_gui(self):
        # --- STYLES ---
        style = ttk.Style()
        style.theme_use("clam")
        
        # Modern "Poppy" Dark Palette
        COLORS = {
            "bg": "#121212",           # Deepest Background
            "panel": "#1e1e1e",        # Card Background
            "header_bg": "#252526",    # Header Background
            "fg": "#e0e0e0",           # Primary Text (Off-white)
            "fg_dim": "#a0a0a0",       # Secondary Text
            "accent": "#3ea6ff",       # Vibrant Blue (YouTube-like)
            "accent_hover": "#62bafe", # Lighter Blue
            "dir_color": "#81d4fa",    # Light Cyan for Directories
            "file_color": "#eeeeee",   # White for Files
            "select": "#264f78",       # Selection Blue
            "input": "#2d2d2d",        # Input Fields
            "border": "#333333",
            "success": "#4caf50",
            "warning": "#ff9800"
        }
        
        # Font Stack (Linux Friendly)
        FONT_MAIN = ("Roboto", 10)
        FONT_BOLD = ("Roboto", 10, "bold")
        FONT_HEADER = ("Roboto", 9, "bold")
        FONT_CODE = ("JetBrains Mono", 10) # Fallback to Monospace/Consolas if needed
        
        self.configure(bg=COLORS["bg"])
        
        # --- TTK STYLING ---
        style.configure(".", background=COLORS["bg"], foreground=COLORS["fg"], font=FONT_MAIN)
        
        # Treeview: Clean, Color Coded
        style.configure("Treeview", 
            background=COLORS["panel"], 
            foreground=COLORS["fg"], 
            fieldbackground=COLORS["panel"], 
            rowheight=32, 
            borderwidth=0,
            font=FONT_MAIN)
            
        style.configure("Treeview.Heading", 
            background=COLORS["header_bg"], 
            foreground=COLORS["accent"], 
            relief="flat", 
            font=FONT_HEADER)
            
        style.map("Treeview", background=[('selected', COLORS["select"])])
        
        # Scrollbar (Dark)
        style.configure("Vertical.TScrollbar", gripcount=0, background=COLORS["panel"], darkcolor=COLORS["panel"], lightcolor=COLORS["panel"], troughcolor=COLORS["bg"], bordercolor=COLORS["bg"], arrowcolor=COLORS["fg"])

        # Buttons: Flat, Modern, Padded
        style.configure("TButton", 
            background=COLORS["panel"], 
            foreground=COLORS["fg"], 
            borderwidth=0, 
            focusthickness=0, 
            font=FONT_BOLD,
            padding=(12, 8))
            
        style.map("TButton", 
            background=[('active', '#333333'), ('pressed', '#1a1a1a')],
            foreground=[('active', '#ffffff')])
        
        # Accent Button (Primary Action)
        style.configure("Accent.TButton", 
            background=COLORS["accent"], 
            foreground="#121212", # Dark text on bright button
            font=("Roboto", 10, "bold"))
            
        style.map("Accent.TButton", 
            background=[('active', COLORS["accent_hover"])])
            
        # Main Layout: PanedWindow with spacing
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, bg=COLORS["bg"], sashwidth=6)
        self.paned_window.pack(fill="both", expand=True, padx=15, pady=15)

        # --- LEFT PANE: Preview ---
        self.frame_left = tk.Frame(self.paned_window, bg=COLORS["panel"])
        self.paned_window.add(self.frame_left, minsize=280)
        
        # Header
        tk.Label(self.frame_left, text="PREVIEW", bg=COLORS["header_bg"], fg=COLORS["accent"], font=FONT_HEADER, anchor="w", padx=10, pady=8).pack(fill="x")
        
        # Metadata Container
        self.meta_frame = tk.Frame(self.frame_left, bg=COLORS["panel"], padx=15, pady=15)
        self.meta_frame.pack(fill="x")
        
        self.meta_label = tk.Label(self.meta_frame, text="Select a file...", justify="left", anchor="w", bg=COLORS["panel"], fg=COLORS["fg_dim"], font=FONT_MAIN)
        self.meta_label.pack(fill="x")
        
        # Separator
        tk.Frame(self.frame_left, bg=COLORS["border"], height=1).pack(fill="x", padx=15)
        
        # Content Area
        self.preview_text = tk.Text(self.frame_left, wrap="word", bg=COLORS["panel"], fg=COLORS["fg"], insertbackground="white", relief="flat", font=FONT_CODE, highlightthickness=0, padx=15, pady=15)
        self.preview_text.pack(expand=True, fill="both")

        # --- MIDDLE PANE: File Explorer ---
        self.frame_mid = tk.Frame(self.paned_window, bg=COLORS["panel"])
        self.paned_window.add(self.frame_mid, minsize=550)
        
        # Header
        header_frame = tk.Frame(self.frame_mid, bg=COLORS["header_bg"], padx=10, pady=8)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="STORAGE", bg=COLORS["header_bg"], fg=COLORS["accent"], font=FONT_HEADER).pack(side="left")
        
        # Path Breadcrumb style
        self.path_label = tk.Label(header_frame, text=self.current_path, bg=COLORS["header_bg"], fg=COLORS["fg_dim"], font=("Roboto", 9))
        self.path_label.pack(side="right")

        # Treeview Container
        tree_frame = tk.Frame(self.frame_mid, bg=COLORS["panel"])
        tree_frame.pack(expand=True, fill="both", padx=0, pady=0)
        
        self.tree = ttk.Treeview(tree_frame, columns=("Size"), show="tree headings", style="Treeview")
        self.tree.heading("#0", text="  Name", anchor="w")
        self.tree.heading("Size", text="Size  ", anchor="e")
        self.tree.column("#0", anchor="w")
        self.tree.column("Size", width=120, anchor="e")
        
        # Configure Tags for Colors
        self.tree.tag_configure('dir', foreground=COLORS["dir_color"], font=FONT_BOLD)
        self.tree.tag_configure('file', foreground=COLORS["file_color"], font=FONT_MAIN)
        
        # Scrollbar
        sb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        
        self.tree.pack(side="left", expand=True, fill="both")
        sb.pack(side="right", fill="y")
        
        # Bindings
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self.on_single_select)
        
        # Navigation Bar
        nav_frame = tk.Frame(self.frame_mid, bg=COLORS["panel"], pady=10, padx=10)
        nav_frame.pack(fill="x")
        
        # Using symbols instead of text for buttons for a cleaner look
        ttk.Button(nav_frame, text="←", command=self.go_back, width=4).pack(side="left", padx=(0, 5))
        ttk.Button(nav_frame, text="→", command=self.go_fwd, width=4).pack(side="left", padx=5)
        ttk.Button(nav_frame, text="⟳ Refresh", command=self.refresh_files).pack(side="left", padx=5)

        # --- RIGHT PANE: AI Command ---
        self.frame_right = tk.Frame(self.paned_window, bg=COLORS["panel"])
        self.paned_window.add(self.frame_right, minsize=300)
        
        # Use Grid layout for Right Pane to ensure input stays at bottom
        self.frame_right.grid_rowconfigure(1, weight=1) # Chat history expands
        self.frame_right.grid_columnconfigure(0, weight=1)
        
        # Header
        header_lbl = tk.Label(self.frame_right, text="NEURAL ASSISTANT", bg=COLORS["header_bg"], fg=COLORS["accent"], font=FONT_HEADER, anchor="w", padx=10, pady=8)
        header_lbl.grid(row=0, column=0, sticky="ew")
        
        self.chat_history = scrolledtext.ScrolledText(self.frame_right, state='disabled', height=10, bg=COLORS["panel"], fg=COLORS["fg"], insertbackground="white", relief="flat", font=("Roboto", 10), highlightthickness=0, borderwidth=0, padx=15, pady=15)
        self.chat_history.grid(row=1, column=0, sticky="nsew")
        
        # Input Area (Fixed at bottom)
        input_container = tk.Frame(self.frame_right, bg=COLORS["panel"], pady=15, padx=15)
        input_container.grid(row=2, column=0, sticky="ew")
        
        # Spinner
        self.spinner_canvas = tk.Canvas(input_container, width=24, height=24, bg=COLORS["panel"], highlightthickness=0)
        self.spinner_canvas.pack(side="top", pady=(0, 10))
        self.spinner_angle = 0
        self.is_loading = False
        
        self.prompt_entry = tk.Entry(input_container, bg=COLORS["input"], fg="#ffffff", insertbackground="white", relief="flat", font=("Roboto", 11))
        self.prompt_entry.pack(fill="x", ipady=10)
        self.prompt_entry.bind("<Return>", self.process_ai_command)
        
        # Send Button with accent
        tk.Frame(input_container, height=10, bg=COLORS["panel"]).pack() # Spacer
        ttk.Button(input_container, text="EXECUTE", command=self.process_ai_command, style="Accent.TButton", width=100).pack(fill="x")
        
        # Store colors
        self.COLORS = COLORS

        # Tray icon setup (if pystray is available)
        if pystray:
            self.after(0, self.setup_tray_icon)
        else:
            self.log_ai("Warning: pystray not installed; tray icon disabled.")

        # Context Menu
        self.context_menu = tk.Menu(self, tearoff=0, bg=COLORS["panel"], fg=COLORS["fg"], font=FONT_MAIN)
        self.context_menu.add_command(label="Download to Local", command=self.download_selection)
        
        self.tree.bind("<Button-3>", self.show_context_menu)

    def connect_ssh(self):
        try:
            # Assumes SSH Key Auth. Use connect(password=...) if needed.
            self.ssh.connect(HOST, username=USER, key_filename=KEY_PATH)
            self.sftp = self.ssh.open_sftp()
            
            # --- DEPLOY HOST FUNCTIONS ---
            # Upload local host_functions.zsh to remote home as .host_functions.zsh
            local_script = "host_functions.zsh"
            remote_script = ".host_functions.zsh" # Hidden file in home
            
            if os.path.exists(local_script):
                try:
                    self.log_ai("System: Deploying host functions to remote...")
                    self.sftp.put(local_script, remote_script)
                except Exception as up_e:
                    self.log_ai(f"Warning: Failed to deploy host_functions.zsh: {up_e}")
            else:
                self.log_ai("Warning: Local host_functions.zsh not found! Remote features may fail.")

            # Fetch FS Overview for AI Context
            # We source the deployed script
            self.fs_context = self.run_remote_command("fs_overview")
            self.log_ai("System: File System Context Loaded.")
            
            self.refresh_files()
            self.log_ai("System: SSH Connected successfully.")
        except Exception as e:
            # Fallback to Local Mode if SSH fails
            response = messagebox.askyesno("Connection Failed", 
                f"SSH Connection failed: {e}\n\nSwitch to Local Mode (no SSH)?")
            if response:
                self.use_local_mode = True
                self.current_path = os.getcwd()
                
                # Fetch Local Overview
                try:
                    home = os.path.expanduser("~")
                    # Emulate fs_overview locally with increased depth
                    cmd = f"find {home} -maxdepth 10 -type d -not -path '*/.*' 2>/dev/null | head -n 500"
                    self.fs_context = subprocess.getoutput(cmd)
                except:
                    self.fs_context = "[Local Overview Unavailable]"
                
                self.log_ai("System: Switched to Local Mode.")
                self.refresh_files()
            else:
                self.destroy()

    def run_remote_command(self, cmd):
        # Helper to run zsh functions
        
        if self.use_local_mode:
            # Run locally via subprocess
            # We construct a command that sources the script then runs the function
            local_script_path = os.path.join(os.getcwd(), "host_functions.zsh")
            full_cmd = f"zsh -c 'source {local_script_path}; {cmd}'"
            try:
                result = subprocess.run(full_cmd, shell=True, capture_output=True, text=True)
                return result.stdout.strip()
            except Exception as e:
                return f"Error: {e}"
        
        # SSH Mode
        # We use the deployed hidden file in home directory
        remote_script_path = "~/.host_functions.zsh"
        
        # We need to source the file every time because the shell context might not persist fully in exec_command 
        # unless we were using an invoke_shell shell. But for this simple request/response, sourcing is safer.
        full_cmd = f"source {remote_script_path}; {cmd}"
        stdin, stdout, stderr = self.ssh.exec_command(full_cmd)
        return stdout.read().decode().strip()

    # --- FILE EXPLORER LOGIC ---
    
    def refresh_files(self, path=None, clear_fwd=True):
        if path and path != self.current_path:
            # Standard navigation clears forward history
            if clear_fwd:
                self.history_fwd.clear()
            self.current_path = path
            
        self.path_label.config(text=self.current_path)
        
        # Clear tree
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Call Host Zsh Function
        raw_data = self.run_remote_command(f"fs_list '{self.current_path}'")
        
        # Parse TYPE|NAME|SIZE
        if raw_data:
            for line in raw_data.split('\n'):
                parts = line.split('|')
                if len(parts) >= 2:
                    ftype, fname, fsize = parts[0], parts[1], parts[2] if len(parts)>2 else "?"
                    
                    # No icons, just color coding tags
                    if ftype == 'd':
                        self.tree.insert("", "end", text=f" {fname}", values=(fsize), tags=('dir', fname))
                    else:
                        self.tree.insert("", "end", text=f" {fname}", values=(fsize), tags=('file', fname))

    def on_double_click(self, event):
        item_id = self.tree.selection()
        if not item_id: return
        item_id = item_id[0]
        
        # In Tkinter Treeview, item() returns a dictionary of options
        item_dict = self.tree.item(item_id)
        tags = item_dict.get("tags", [])
        
        # Tags is a list/tuple of strings. e.g. ['dir', 'MyFolder']
        if 'dir' in tags:
            # Find name. It is the second element in our logic: tags=('dir', fname)
            if len(tags) >= 2:
                dirname = tags[1]
                new_path = os.path.join(self.current_path, dirname)
                self.refresh_files(new_path)

    def go_back(self):
        # Hierarchical Back (Up to Parent)
        parent = os.path.dirname(self.current_path)
        if parent != self.current_path:
            # Push current to fwd history so we can return
            self.history_fwd.append(self.current_path)
            self.refresh_files(parent, clear_fwd=False)

    def go_fwd(self):
        # Return to previously visited child (if we just went back)
        if self.history_fwd:
            nxt = self.history_fwd.pop()
            self.refresh_files(nxt, clear_fwd=False)

    def go_up(self):
        # Alias for back
        self.go_back()

    def on_single_select(self, event):
        # Update Left Preview Pane
        item_id = self.tree.selection()
        if not item_id: return
        item_id = item_id[0]
        
        item_dict = self.tree.item(item_id)
        tags = item_dict.get("tags", [])
        
        # Safety check
        if not tags or len(tags) < 2: return
        
        ftype = tags[0] # 'dir' or 'file'
        filename = tags[1]
        
        # Get basic info
        full_path = os.path.join(self.current_path, filename)
        
        # Get file size
        try:
            file_size = item_dict.get("values", ["?"])[0]
        except:
            file_size = "?"
        
        # Update Metadata Label ALWAYS
        # Use safe colors from palette
        accent = self.COLORS["accent"]
        fg = self.COLORS["fg"]
        
        if ftype == 'file':
             meta_text = f"FILE: {filename}\nPATH: {full_path}\nSIZE: {file_size}"
             self.meta_label.config(text=meta_text, fg=accent)
        else:
             meta_text = f"DIRECTORY: {filename}\nPATH: {full_path}"
             self.meta_label.config(text=meta_text, fg=fg)
        
        # Clear previous preview
        self.preview_text.delete(1.0, tk.END)
        for widget in self.frame_left.winfo_children():
            if isinstance(widget, tk.Label) and hasattr(widget, 'image'):
                widget.destroy()
        
        self.preview_text.pack(expand=True, fill="both", padx=15, pady=15)

        if ftype == 'file':
            ext = os.path.splitext(filename)[1].lower()
            
            # --- IMAGE PREVIEW ---
            if ext in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.ico', '.webp']:
                if HAS_IMAGE_TK:
                    self.show_image_preview(full_path)
                else:
                    self.preview_text.insert(tk.END, "[Image Preview Disabled - Missing PIL.ImageTk]")
                return

            # --- TEXT/CODE PREVIEW ---
            try:
                if self.use_local_mode:
                    with open(full_path, 'r', errors='ignore') as f:
                         content = f.read(4096)
                else:
                    content = self.run_remote_command(f"head -n 50 '{full_path}'")

                self.preview_text.insert(tk.END, content)
            except Exception as e:
                self.preview_text.insert(tk.END, f"[Binary/Unreadable File]\nError: {e}")

        else:
            self.preview_text.insert(tk.END, "[Directory Selected]")

    def show_image_preview(self, path):
        try:
            # Hide text widget
            self.preview_text.pack_forget()
            
            # Load Image
            if self.use_local_mode:
                img_data = Image.open(path)
            else:
                # Remote image: download to memory buffer
                with self.sftp.open(path, 'rb') as f:
                    img_bytes = f.read()
                img_data = Image.open(io.BytesIO(img_bytes))
            
            # Resize thumbnail
            img_data.thumbnail((300, 300))
            photo = ImageTk.PhotoImage(img_data)
            
            lbl = tk.Label(self.frame_left, image=photo, bg=self.COLORS["panel"])
            lbl.image = photo # Keep reference
            lbl.pack(expand=True, padx=5, pady=5)
            
        except Exception as e:
            self.preview_text.pack(expand=True, fill="both")
            self.preview_text.insert(tk.END, f"[Image Preview Failed: {e}]")

    # --- AI & LOGIC ---

    def log_ai(self, text):
        self.chat_history.config(state='normal')
        self.chat_history.insert(tk.END, text + "\n\n")
        self.chat_history.see(tk.END)
        self.chat_history.config(state='disabled')

    def process_ai_command(self, event=None):
        user_input = self.prompt_entry.get()
        if not user_input: return
        self.prompt_entry.delete(0, tk.END)
        self.log_ai(f"You: {user_input}")
        
        # Start Loading Animation
        self.start_loading_animation()
        
        # Run AI in background thread to avoid freezing UI
        threading.Thread(target=self.run_ai_thread, args=(user_input,), daemon=True).start()

    def start_loading_animation(self):
        self.is_loading = True
        self.spinner_canvas.pack(pady=5) # Show canvas
        self.animate_spinner()

    def animate_spinner(self):
        if not self.is_loading: return
        
        self.spinner_canvas.delete("all")
        w, h = 24, 24
        x, y = w/2, h/2
        radius = 8
        extent = 120
        start = self.spinner_angle
        
        # Draw rotating arc with Accent Color
        color = self.COLORS["accent"]
        self.spinner_canvas.create_arc(x-radius, y-radius, x+radius, y+radius, 
                                     start=start, extent=extent, style="arc", width=3, outline=color)
        self.spinner_canvas.create_arc(x-radius, y-radius, x+radius, y+radius, 
                                     start=start+180, extent=extent, style="arc", width=3, outline=color)
        
        self.spinner_angle = (self.spinner_angle - 25) % 360 # Faster
        self.loading_anim_id = self.after(30, self.animate_spinner)

    def stop_loading_animation(self):
        self.is_loading = False
        self.spinner_canvas.delete("all")
        self.spinner_canvas.pack_forget() # Hide canvas
        if hasattr(self, 'loading_anim_id'):
             self.after_cancel(self.loading_anim_id)

    def run_ai_thread(self, user_input):
        # Construct Prompt for OpenAI
        # We tell GPT to output JSON so we can execute code programmatically
        system_prompt = f"""
        You are a file manager assistant. 
        
        CONTEXT:
        Current Path: '{self.current_path}'
        File System Overview:
        {self.fs_context}
        
        Interpret the user request. Use the Overview to infer paths.
        
        Return ONLY a valid JSON object. Do not add markdown formatting.
        
        Possible actions:
        1. "search": finds a file. Params: "query".
        2. "copy": copies a file. Params: "source", "destination", "direction" (to_host or to_client).
        3. "navigate": changes directory. Params: "path".
        4. "question": ask the user for clarification. Params: "text".
        
        Example: {{"action": "search", "params": {{"query": "tax_report"}} }}
        Example: {{"action": "question", "params": {{"text": "Did you mean the 2023 or 2024 report?"}} }}
        """

        try:
            response = self.ai_client.chat.completions.create(
                model="gpt-5-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ]
            )
            ai_reply = response.choices[0].message.content
            
            # Schedule execution on main thread
            self.after(0, lambda: self.handle_ai_response(ai_reply))
            
        except Exception as e:
            self.after(0, lambda: self.stop_loading_animation())
            self.after(0, lambda: self.log_ai(f"Error: {e}"))

    def handle_ai_response(self, ai_reply):
        self.stop_loading_animation()
        try:
            action_data = json.loads(ai_reply)
            self.execute_ai_action(action_data)
        except Exception as e:
            self.log_ai(f"Error parsing AI response: {e}\nRaw: {ai_reply}")

    def execute_ai_action(self, data):
        action = data.get("action")
        params = data.get("params")

        if action == "question":
            # AI needs clarification
            question_text = params.get("text")
            self.log_ai(f"AI: {question_text}")
            
            # Use simpledialog to get answer, or just let user type in chat
            # Since we have a chat interface, we can just print it and wait for user input
            # But to make it obvious, we can focus the entry
            self.prompt_entry.focus_set()
            return

        if action == "navigate":
            self.refresh_files(params["path"])
            self.log_ai(f"AI: Navigated to {params['path']}")

        elif action == "search":
            self.log_ai(f"AI: Searching for '{params['query']}'...")
            
            # Use host zsh search with error capturing
            # Note: We use "." as search path if current path is root-like or empty
            search_base = self.current_path if self.current_path else "."
            
            # Debug:
            # self.log_ai(f"Debug: find '{search_base}' -name '*{params['query']}*'")
            
            results = self.run_remote_command(f"fs_search '{params['query']}' '{search_base}'")
            
            if not results:
                 self.log_ai("AI: No results found in current directory. Trying Home directory...")
                 home_path = os.path.expanduser("~")
                 results = self.run_remote_command(f"fs_search '{params['query']}' '{home_path}'")
                 
                 if not results:
                     self.log_ai("AI: No results found in Home directory either.")
                 else:
                     self.log_ai(f"Results (from Home):\n{results}")

            else:
                 self.log_ai(f"Results:\n{results}")
            
            # Logic: If result found, parse valid paths
            if results and "|" in results:
                # Format: TYPE|PATH|SIZE
                lines = results.strip().split('\n')
                if lines:
                     # Just grab the first valid match
                     first_match_parts = lines[0].split('|')
                     if len(first_match_parts) >= 2:
                         full_path = first_match_parts[1]
                         parent_dir = os.path.dirname(full_path)
                         
                         self.log_ai(f"AI: Found match at {full_path}")
                         self.log_ai(f"AI: Navigating to context: {parent_dir}")
                         
                         # Navigate to the directory containing the file
                         self.refresh_files(parent_dir)
                         
                         # Select the file in the tree
                         target_name = os.path.basename(full_path)
                         for item in self.tree.get_children():
                             item_text = self.tree.item(item, "text")
                             # Text includes icon, so check tags or end of string
                             tags = self.tree.item(item, "tags")
                             if tags and len(tags) >= 2 and tags[1] == target_name:
                                 self.tree.selection_set(item)
                                 self.tree.focus(item)
                                 self.tree.see(item)
                                 # Trigger selection event manually to update preview
                                 self.on_single_select(None)
                                 break
            
        elif action == "copy":
            src = params.get("source")
            dest = params.get("destination")
            direction = params.get("direction")
            
            # --- DOUBLE PERMISSION LOGIC ---
            confirm1 = messagebox.askyesno("Permission Request 1/2", 
                f"AI wants to copy:\n{src} -> {dest}\n\nAllow initial access?")
            
            if confirm1:
                confirm2 = messagebox.askwarning("Final Authorization 2/2", 
                    "Confirming Write Operation.\nThis action is irreversible.\nProceed?")
                
                if confirm2:
                    self.perform_copy(src, dest, direction)
                else:
                    self.log_ai("System: Copy Aborted at stage 2.")
            else:
                self.log_ai("System: Copy Aborted at stage 1.")

    def perform_copy(self, src, dest, direction):
        try:
            if self.use_local_mode:
                # Local copy using shutil (or just cp command via subprocess)
                # Since we are local, both src and dest are local paths.
                # "direction" is meaningless in local mode, but we'll assume it's just a copy.
                import shutil
                shutil.copy2(src, dest)
                self.log_ai(f"Success: Copied {src} to {dest} (Local)")
                self.refresh_files()
                return

            if direction == "to_client":
                self.sftp.get(src, dest)
                self.log_ai(f"Success: Downloaded {src} to {dest}")
            elif direction == "to_host":
                self.sftp.put(src, dest)
                self.refresh_files() # Refresh view
                self.log_ai(f"Success: Uploaded {src} to {dest}")
        except Exception as e:
            self.log_ai(f"Copy Failed: {e}")

    # --- CONTEXT MENU ACTIONS ---
    def show_context_menu(self, event):
        # Select item under cursor
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.post(event.x_root, event.y_root)

    def download_selection(self):
        item_id = self.tree.selection()
        if not item_id: return
        item_id = item_id[0]
        
        item_dict = self.tree.item(item_id)
        tags = item_dict.get("tags", [])
        
        if not tags or len(tags) < 2: return
        
        ftype = tags[0]
        filename = tags[1]
        full_path = os.path.join(self.current_path, filename)
        
        if ftype == 'dir':
            messagebox.showwarning("Not Supported", "Directory download is not supported yet.\nPlease select a file.")
            return
            
        # Ask for save location
        dest_path = filedialog.asksaveasfilename(initialfile=filename, title="Save File")
        if dest_path:
            # Run in thread to not block UI
            threading.Thread(target=self.perform_manual_download, args=(full_path, dest_path), daemon=True).start()

    def perform_manual_download(self, src, dest):
        try:
            self.log_ai(f"System: Starting download of {src}...")
            if self.use_local_mode:
                import shutil
                shutil.copy2(src, dest)
            else:
                self.sftp.get(src, dest)
            
            self.log_ai(f"Success: Downloaded to {dest}")
            # Use after to show messagebox in main thread
            self.after(0, lambda: messagebox.showinfo("Download Complete", f"File saved to:\n{dest}"))
        except Exception as e:
            self.log_ai(f"Error: {e}")
            self.after(0, lambda: messagebox.showerror("Download Failed", str(e)))

    # --- TRAY ICON & WINDOW CONTROL ---
    def setup_tray_icon(self):
        if not pystray:
            return
        if self.tray_running:
            return
        try:
            icon_size = 64
            img = Image.new("RGBA", (icon_size, icon_size), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            # Outer circle
            draw.ellipse((4, 4, icon_size - 4, icon_size - 4), fill=self.COLORS["accent"])
            # Inner cross
            draw.rectangle((icon_size//2 - 8, icon_size//2 - 14, icon_size//2 + 8, icon_size//2 + 14), fill=self.COLORS["bg"])
            draw.rectangle((icon_size//2 - 14, icon_size//2 - 8, icon_size//2 + 14, icon_size//2 + 8), fill=self.COLORS["bg"])

            menu = pystray.Menu(
                pystray.MenuItem("Show/Hide", self.toggle_window),
                pystray.MenuItem("New Window", self.show_window),
                pystray.MenuItem("Quick Surf", self.quick_prompt_window),
                pystray.MenuItem("Exit", self.tray_exit)
            )
            self.tray_icon = pystray.Icon("Neural SSH", img, "Neural SSH Explorer", menu)
            self.tray_running = True
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as e:
            self.log_ai(f"Warning: Tray icon failed: {e}")

    def toggle_window(self, *args):
        self.after(0, lambda: (self.show_window() if self.state() == 'withdrawn' else self.hide_to_tray()))

    def show_window(self, *args):
        self.after(0, self._show_window_now)

    def _show_window_now(self):
        self.deiconify()
        self.lift()
        try:
            self.focus_force()
        except:
            pass

    def hide_to_tray(self):
        self.withdraw()

    def on_close(self):
        # Instead of closing, hide to tray if available
        if pystray:
            self.hide_to_tray()
        else:
            self.destroy()

    def quick_prompt_window(self, *args):
        # Minimal, no-button prompt; Enter submits; Escape cancels.
        def _show():
            top = tk.Toplevel(self)
            top.title("Quick Prompt")
            top.configure(bg=self.COLORS["panel"])
            top.resizable(False, False)
            top.geometry("420x120+200+200")
            top.attributes("-topmost", True)

            entry = tk.Entry(top, bg=self.COLORS["input"], fg="#ffffff", insertbackground="white",
                             relief="flat", font=("Roboto", 11))
            entry.pack(fill="x", padx=14, pady=(20, 10), ipady=8)
            entry.focus_set()

            def submit(event=None):
                prompt = entry.get().strip()
                top.destroy()
                if prompt:
                    self._show_window_now()
                    self.prompt_entry.delete(0, tk.END)
                    self.prompt_entry.insert(0, prompt)
                    self.process_ai_command()

            def cancel(event=None):
                top.destroy()

            entry.bind("<Return>", submit)
            entry.bind("<Escape>", cancel)

        self.after(0, _show)

    def tray_exit(self, *args):
        def _exit():
            try:
                if self.tray_icon:
                    self.tray_icon.stop()
            except:
                pass
            self.tray_running = False
            self.destroy()
        self.after(0, _exit)

if __name__ == "__main__":
    app = RemoteExplorer()
    app.mainloop()


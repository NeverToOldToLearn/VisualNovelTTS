import os
import re
import time
import shutil
import pygame
import pyperclip
import logging
import requests
import hashlib
import tempfile
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox, Listbox, Scrollbar
import threading
import json
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class EchoVNTTS:
    def __init__(self):
        self.config_file = "vntts_config.json"
        # Default voice model (same for all, multi-speaker)
        self.voice_model_path = r"C:\Piper\Voices\en_US-libritts_r-medium\en_US-libritts_r-medium.onnx"
        # Max speakers
        self.max_speakers = 6
        # Fixed synthesis parameters (to avoid distortion)
        self.synthesis_params = {'length_scale': 1.0, 'noise_scale': 0.333, 'noise_w': 0.333}
        # Speaker configs (only IDs matter now)
        self.speaker_configs = {
            f'Speaker{i}': {'id': 198 + (i-1)*10} for i in range(1, self.max_speakers + 1)
        }
        # Name to speaker mapping
        self.name_to_speaker = {
            'Rick': 'Speaker1',
        }
        self.override_speaker = None
        self.last_text = ""
        self.output_file = r"C:\Piper\vn_tts_echo.wav"
        self.is_processing = False
        self.lm_studio_url = "http://127.0.0.1:1234/v1/chat/completions"
        self.lm_model = "darkidol-llama-3.1-8b-instruct-1.2-uncensored"
        self.enable_llm = False
        self.cache_dir = r"C:\Piper\cache"
        os.makedirs(self.cache_dir, exist_ok=True)
        self.short_whitelist = [
            "I", "I'm", "Yes", "No", "What?", "Huh?", "Okay.", "Sure.", "Why?", "How?", "Thanks.", "Sorry.", "Hey!", "Wait!", "Stop!", "Go.", "Run!", "Help!",
        ]
        try:
            pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=256)
        except Exception as e:
            logger.error(f"Failed to initialize pygame mixer: {e}")

        # Load config if exists
        self.load_config()

        self.enable_gui = True

    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                self.speaker_configs = config.get('speaker_configs', self.speaker_configs)
                self.name_to_speaker = config.get('name_to_speaker', self.name_to_speaker)
                logger.info("Loaded config from JSON")
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

    def save_config(self):
        config = {
            'speaker_configs': self.speaker_configs,
            'name_to_speaker': self.name_to_speaker
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
            logger.info("Saved config to JSON")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def launch_gui(self):
        self.gui_root = tk.Tk()
        self.gui_root.title("VisualNovelTTS - Character Name Manager")
        self.gui_root.geometry("600x500")

        # Main frame
        main_frame = ttk.Frame(self.gui_root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        self.gui_root.columnconfigure(0, weight=1)
        self.gui_root.rowconfigure(0, weight=1)

        # Override speaker section
        override_frame = ttk.LabelFrame(main_frame, text="Override Speaker (for testing)", padding="10")
        override_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Label(override_frame, text="Force all dialogue to use:").grid(row=0, column=0, padx=5)
        self.speaker_var = tk.StringVar(value='None')
        ttk.Combobox(override_frame, textvariable=self.speaker_var, 
                     values=('None',) + tuple(self.speaker_configs.keys()), 
                     state='readonly', width=15).grid(row=0, column=1, padx=5)

        # Speaker ID configuration
        speaker_frame = ttk.LabelFrame(main_frame, text="Speaker Voice IDs (1-902)", padding="10")
        speaker_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.speaker_id_entries = {}
        for i, speaker in enumerate(sorted(self.speaker_configs.keys())):
            ttk.Label(speaker_frame, text=f"{speaker}:").grid(row=i//3, column=(i%3)*2, padx=5, pady=2, sticky=tk.E)
            id_entry = ttk.Entry(speaker_frame, width=10)
            id_entry.insert(0, str(self.speaker_configs[speaker]['id']))
            id_entry.grid(row=i//3, column=(i%3)*2+1, padx=5, pady=2)
            self.speaker_id_entries[speaker] = id_entry

        # Character name mappings section
        names_frame = ttk.LabelFrame(main_frame, text="Character Name → Speaker Assignments", padding="10")
        names_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        main_frame.rowconfigure(2, weight=1)

        # Listbox with scrollbar
        list_frame = ttk.Frame(names_frame)
        list_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))
        names_frame.rowconfigure(0, weight=1)
        
        scrollbar = Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.names_listbox = Listbox(list_frame, height=8, yscrollcommand=scrollbar.set)
        self.names_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.names_listbox.yview)
        self.update_names_listbox()

        # Edit controls
        ttk.Label(names_frame, text="Character Name:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.E)
        self.name_entry = ttk.Entry(names_frame, width=20)
        self.name_entry.grid(row=1, column=1, padx=5, pady=5)
        
        ttk.Label(names_frame, text="Speaker:").grid(row=2, column=0, padx=5, pady=5, sticky=tk.E)
        self.assign_var = tk.StringVar(value='Speaker1')
        speaker_dropdown = ttk.Combobox(names_frame, textvariable=self.assign_var, 
                                       values=tuple(sorted(self.speaker_configs.keys())), 
                                       state='readonly', width=17)
        speaker_dropdown.grid(row=2, column=1, padx=5, pady=5)

        # Buttons for name management
        button_frame = ttk.Frame(names_frame)
        button_frame.grid(row=3, column=0, columnspan=3, pady=5)
        
        ttk.Button(button_frame, text="Add/Update", command=self.add_update_name, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Delete Selected", command=self.delete_name, width=15).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Selection", command=self.clear_selection, width=15).pack(side=tk.LEFT, padx=5)

        self.names_listbox.bind('<<ListboxSelect>>', self.on_name_select)

        # Bottom buttons
        bottom_frame = ttk.Frame(main_frame)
        bottom_frame.grid(row=3, column=0, columnspan=3, pady=10)
        
        ttk.Button(bottom_frame, text="Apply & Save", command=self.apply_configuration, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="Apply & Restart", command=self.apply_and_restart, width=20).pack(side=tk.LEFT, padx=5)

        self.gui_root.protocol("WM_DELETE_WINDOW", self.on_gui_close)

    def update_names_listbox(self):
        self.names_listbox.delete(0, tk.END)
        for name, speaker in sorted(self.name_to_speaker.items()):
            self.names_listbox.insert(tk.END, f"{name} → {speaker}")

    def on_name_select(self, event):
        selection = self.names_listbox.curselection()
        if selection:
            selected = self.names_listbox.get(selection[0])
            name = selected.split(' → ')[0]
            self.name_entry.delete(0, tk.END)
            self.name_entry.insert(0, name)
            speaker = self.name_to_speaker[name]
            self.assign_var.set(speaker)

    def add_update_name(self):
        name = self.name_entry.get().strip()
        speaker = self.assign_var.get()
        if name and speaker in self.speaker_configs:
            self.name_to_speaker[name] = speaker
            self.update_names_listbox()
            messagebox.showinfo("Success", f"Assigned: {name} → {speaker}")
            self.clear_selection()
        else:
            messagebox.showerror("Error", "Invalid name or speaker")

    def delete_name(self):
        selection = self.names_listbox.curselection()
        if selection:
            selected = self.names_listbox.get(selection[0])
            name = selected.split(' → ')[0]
            if messagebox.askyesno("Confirm Delete", f"Delete mapping for '{name}'?"):
                del self.name_to_speaker[name]
                self.update_names_listbox()
                self.clear_selection()
                messagebox.showinfo("Deleted", f"Removed mapping for '{name}'")
        else:
            messagebox.showwarning("No Selection", "Please select a name to delete")

    def clear_selection(self):
        self.names_listbox.selection_clear(0, tk.END)
        self.name_entry.delete(0, tk.END)
        self.assign_var.set('Speaker1')

    def apply_configuration(self):
        try:
            # Update override
            self.override_speaker = self.speaker_var.get() if self.speaker_var.get() != 'None' else None
            
            # Update speaker IDs
            for speaker, entry in self.speaker_id_entries.items():
                speaker_id = int(entry.get())
                if not (1 <= speaker_id <= 902):
                    raise ValueError(f"Speaker ID for {speaker} must be between 1 and 902")
                self.speaker_configs[speaker]['id'] = speaker_id
            
            self.save_config()
            messagebox.showinfo("Success", "Configuration applied and saved!")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def apply_and_restart(self):
        self.apply_configuration()
        logger.info("Restarting script...")
        os.execv(sys.executable, [sys.executable] + sys.argv)

    def on_gui_close(self):
        self.gui_root.destroy()
        os._exit(0)

    def clean_dialog_text(self, raw_text: str) -> str:
        if not raw_text or not raw_text.strip():
            return ""

        text = raw_text.strip()

        # Remove common VN formatting
        text = re.sub(r'\{[^}]+\}', '', text)
        text = re.sub(r'\[[^]]*\](?!:)', '', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'\*([^*]+)\*', r'\1', text)
        
        # Process speaker tags
        speaker_match = re.match(r'^\[(Speaker\d+|default)\]:\s*(.*)$', text, re.IGNORECASE)
        if speaker_match:
            speaker, content = speaker_match.groups()
            return f"[{speaker}]: {content.strip()}" if content.strip() else ""

        # Process character names
        for name, speaker in self.name_to_speaker.items():
            if text.lower().startswith(f"{name.lower()}:"):
                content = text[len(name)+1:].strip()
                return f"[{speaker}]: {content}" if content else ""

        return text

    def enrich_with_llm(self, content):
        if not content.strip():
            logger.info("Skipping LLM: Input is empty or punctuation only")
            return ""
        if len(content.split()) <= 2:
            logger.info(f"Short input detected: {content}, adding punctuation only")
            return content + "." if not content.endswith((".", "!", "?")) else content
        try:
            body = {
                "model": self.lm_model,
                "messages": [
                    {"role": "system", "content": "You are a text processor for TTS optimization using Piper (en_US-libritts_r-medium.onnx). Your only task is to take the input text, add punctuation for natural pauses and emphasis (e.g., commas for short pauses, periods or ellipses for longer ones), and normalize filler sounds or onomatopoeia to forms that sound human-like when spoken (e.g., change 'Hmmm' to 'Hum', 'Uhhh' to 'Uh', without changing the intended meaning or adding/removing content). Do not explain, do not add stories, do not discuss with yourself, do not output anything except the processed text."},
                    {"role": "user", "content": f"Add punctuation to this text: {content}"}
                ],
                "temperature": 0.0,
                "max_tokens": 200,
                "presence_penalty": 1.0
            }
            response = requests.post(self.lm_studio_url, json=body, timeout=10)
            if response.status_code == 200:
                enriched = response.json()["choices"][0]["message"]["content"].strip()
                logger.info(f"Raw LLM output: '{enriched}'")
                enriched = re.sub(r'\s*\(No punctuation added\)\s*', '', enriched).strip()
                enriched = re.sub(r'^Output:\s*', '', enriched).strip()
                return enriched
            else:
                logger.warning("LLM API failed, using original")
                return content
        except Exception as e:
            logger.error(f"LLM error: {e}")
            return content

    def get_voice_model(self, text):
        if self.override_speaker:
            clean_text = text.replace(f"[{self.override_speaker}]:", "").strip() if text.startswith(f"[{self.override_speaker}]:") else text
            logger.info(f"Using GUI override speaker: {self.override_speaker}")
            return self.voice_model_path, clean_text, self.override_speaker

        for speaker in self.speaker_configs:
            if text.startswith(f"[{speaker}]:"):
                clean_text = text.replace(f"[{speaker}]:", "").strip()
                logger.info(f"Speaker detected: {speaker}")
                return self.voice_model_path, clean_text, speaker

        for name, speaker in self.name_to_speaker.items():
            if text.lower().startswith(f"{name.lower()}:"):
                clean_text = text[len(name)+1:].strip()
                logger.info(f"Character name detected: {name} -> {speaker}")
                return self.voice_model_path, clean_text, speaker

        return self.voice_model_path, text, 'default'

    def process_text(self, text):
        if self.is_processing:
            logger.info("Already processing, skipping...")
            return
        self.is_processing = True
        logger.info(f"Processing: {text[:50]}...")

        try:
            speaker_tag = None
            content = text
            match = re.match(r'^\[(Speaker\d+|default)\]:\s*(.*)$', text, re.IGNORECASE)
            if match:
                speaker_tag = f"[{match.group(1)}]: "
                content = match.group(2).strip()

            enriched_content = self.enrich_with_llm(content) if self.enable_llm else content

            if not enriched_content:
                logger.info("No text to process after enrichment")
                self.is_processing = False
                return

            enriched_text = f"{speaker_tag}{enriched_content}" if speaker_tag else enriched_content

            model_path, clean_text, speaker = self.get_voice_model(enriched_text)

            hash_key = hashlib.md5((clean_text + speaker).encode()).hexdigest()
            cached_file = os.path.join(self.cache_dir, f"{hash_key}.wav")
            if os.path.exists(cached_file):
                logger.info(f"Using cached .wav: {cached_file}")
                shutil.copyfile(cached_file, self.output_file)
            else:
                if os.path.exists(self.output_file):
                    try:
                        os.remove(self.output_file)
                    except Exception as e:
                        logger.warning(f"Could not remove output file: {e}")

                # Use fixed synthesis params and per-speaker ID
                speaker_id = self.speaker_configs.get(speaker, {'id': 0})['id'] if speaker != 'default' else 0
                ls = self.synthesis_params['length_scale']
                ns = self.synthesis_params['noise_scale']
                nw = self.synthesis_params['noise_w']
                
                temp_dir = r"C:\Piper\temp"
                os.makedirs(temp_dir, exist_ok=True)
                try:
                    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8', dir=temp_dir) as temp_file:
                        temp_file.write(clean_text)
                        temp_file_path = temp_file.name
                except Exception as e:
                    logger.error(f"Failed to create temp file: {e}")
                    self.is_processing = False
                    return

                cmd_str = f'type "{temp_file_path}" | "E:\\Piper\\piper.exe" -m "{model_path}" -f "{self.output_file}" --speaker {speaker_id} --length_scale {ls} --noise_scale {ns} --noise_w {nw}'
                logger.info(f"Running command: {cmd_str}")
                try:
                    result = subprocess.run(
                        cmd_str,
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=r"C:\Piper",
                        timeout=30
                    )
                except Exception as e:
                    logger.error(f"Subprocess error: {e}")
                    self.is_processing = False
                    try:
                        os.unlink(temp_file_path)
                    except Exception:
                        pass
                    return

                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Could not delete temp file: {e}")

                if result.returncode != 0 or not os.path.exists(self.output_file) or os.path.getsize(self.output_file) == 0:
                    logger.error(f"Audio generation failed: return code {result.returncode}")
                    logger.error(f"Stdout: {result.stdout}")
                    logger.error(f"Stderr: {result.stderr}")
                    self.is_processing = False
                    return
                try:
                    shutil.copyfile(self.output_file, cached_file)
                    logger.info(f"Cached new .wav: {cached_file}")
                except Exception as e:
                    logger.warning(f"Could not cache .wav: {e}")

            try:
                sound = pygame.mixer.Sound(self.output_file)
                sound.set_volume(1.0)
                sound.play()
                audio_length = sound.get_length()
                logger.info(f"Audio length: {audio_length:.2f}s")
                time.sleep(audio_length)
                logger.info("Playback done")
            except Exception as e:
                logger.error(f"Playback error: {e}")

        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            self.is_processing = False

    def check_clipboard(self):
        try:
            clipboard_text = pyperclip.paste()

            if not clipboard_text:
                logger.debug("Empty clipboard content")
                return

            text = clipboard_text.strip()

            if any(text.lower().startswith(phrase.lower()) for phrase in self.short_whitelist) or re.match(r'^[A-Za-z]{1,2}[.!?]?$', text):
                is_vn_text = True
            else:
                if len(text) < 2:
                    logger.debug(f"Rejected short text: '{text}'")
                    return

                vn_patterns = [
                    r"\[.*?\]",
                    r"\{.*?\}",
                    r".*?:",
                    r"「.*?」"
                ]
                is_vn_text = any(re.search(pattern, text) for pattern in vn_patterns)

            cleaned_text = self.clean_dialog_text(text)

            if cleaned_text != self.last_text and cleaned_text:
                if is_vn_text or len(cleaned_text) >= 2:
                    logger.info(f"Processing VN/short text: '{text[:50]}...'")
                else:
                    logger.debug(f"Processing potential dialogue: '{text[:50]}...'")
                self.process_text(cleaned_text)
                self.last_text = cleaned_text
            else:
                logger.debug(f"Skipped duplicate or empty text")

        except Exception as e:
            logger.error(f"Clipboard error: {e}")

    def polling_loop(self):
        logger.info("Starting clipboard polling loop...")
        
        last_check = time.time()
        min_interval = 0.1

        try:
            while True:
                current_time = time.time()
                if current_time - last_check >= min_interval:
                    self.check_clipboard()
                    last_check = current_time
                time.sleep(0.01)
        except KeyboardInterrupt:
            logger.info("Polling loop stopped")

    def run(self):
        logger.info("Starting LLM-Enhanced VN TTS...")
        logger.info("Press Ctrl+C to stop. Ollama must be running!")
        logger.info("Clipboard polling mode enabled")

        try:
            if self.enable_gui:
                self.launch_gui()
                polling_thread = threading.Thread(target=self.polling_loop, daemon=True)
                polling_thread.start()
                self.gui_root.mainloop()
            else:
                self.polling_loop()
        except KeyboardInterrupt:
            logger.info("Stopping...")
        finally:
            pygame.mixer.quit()

if __name__ == "__main__":
    tts = EchoVNTTS()
    tts.run()

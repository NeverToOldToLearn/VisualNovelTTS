# VisualNovelTTS - LLM-Enhanced TTS for Visual Novels

## Overview
VisualNovelTTS is a text-to-speech (TTS) tool designed specifically for visual novel dialogue, combining **Piper TTS** with optional **LLM enhancement** via LM Studio. It provides:
- Speaker configuration management GUI
- Clipboard monitoring for automatic dialogue processing
- Local WAV caching for performance optimization
- Modular architecture supporting multiple speakers and text enhancements

## Key Features
✅ **Piper TTS Integration**  
Uses `en_US-libritts_r-medium.onnx` model with fixed synthesis parameters for consistent audio quality

✅ **LLM Text Enhancement**  
Optional integration with LM Studio (localhost:1234) to add natural punctuation and optimize text for TTS

✅ **Speaker Management GUI**  
Configure speaker IDs, map character names to speakers, and override settings for testing

✅ **Clipboard Monitoring**  
Automatically processes dialogue from clipboard using configurable patterns

## Getting Started

### Prerequisites
- Python 3.8+
- [Piper TTS model](https://github.com/CorentinJ/PyTorch-TTS/tree/master/piper) (`en_US-libritts_r-medium.onnx`)
- LM Studio running locally at `http://127.0.0.1:1234`
- Required libraries:
  ```bash
  pip install piper pyperclip pygame requests hashlib tkinter
  ```

### Setup Instructions
1. Place Piper model files in a directory (e.g., `C:\Piper\Voices`)
2. Ensure LM Studio is running locally
3. Modify configuration paths in the script as needed

## Usage
1. **Run the application**:
   ```python
   python VisualNovelTTS.py
   ```
2. **GUI Features**:
   - Configure speaker IDs (1-902)
   - Map character names to speakers
   - Enable/disable LLM enhancement
   - Force override speaker for testing

3. **Clipboard Monitoring**:
   - Supported patterns: `[SpeakerX]:`, `CharacterName:` and common VN formatting
   - Automatically processes text from clipboard with configurable rules

## Configuration
### Speaker Settings
- Modify `speaker_configs` in the code to set custom speaker IDs
- Map character names using the GUI or `vntts_config.json`

### LLM Settings
```python
self.lm_studio_url = "http://127.0.0.1:1234/v1/chat/completions"
self.lm_model = "darkidol-llama-3.1-8b-instruct-1.2-uncensored"
```

## Troubleshooting
- **Missing models**: Ensure Piper model path is correctly configured
- **LM Studio not running**: Verify localhost:1234 is accessible
- **Audio issues**: Check permissions for `C:\Piper\` directory

## License
MIT License - See LICENSE file for details

## Contributing
Fork the project and submit pull requests for improvements or bug fixes.

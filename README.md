# 🐬 Animal Crossing LLM Mod

**Transform Animal Crossing into an AI-powered conversation experience!** This mod uses Large Language Models to generate dynamic, contextual dialogue for villagers in real-time.

> ⚠️ **EXPERIMENTAL SOFTWARE**: This mod has known bugs and is only tested on macOS. Use at your own risk! PRs welcome to help improve it.

## 🎥 What This Does

Ever wanted to have meaningful conversations with your Animal Crossing villagers? This mod:
- **Reads dialogue memory** from Animal Crossing running in Dolphin emulator
- **Generates AI responses** using Google Gemini, OpenAI or Anthropic Claude models
- **Writes new dialogue** back to the game in real-time
- **Creates dynamic conversations** that feel natural and contextual

## 🚀 Quick Start (For YouTube Viewers)

### 1. Install Python & Dependencies
```bash
# Install Python 3.10+ from python.org
# Then install dependencies
pip install -r requirements.txt
```

### 2. Setup Environment Variables
Create a `.env` file in the project folder:
```bash
# For Google Gemini (Free tier available)
GOOGLE_API_KEY=your_api_key_here

# For OpenAI (Paid)
OPENAI_API_KEY=your_api_key_here

# For Anthropic Claude (Paid, fastest)
ANTHROPIC_API_KEY=your_api_key_here
MODEL_PROVIDER=anthropic

# Optional: Enable features
ENABLE_SCREENSHOT=1
ENABLE_GOSSIP=1
GENERATION_SUPPRESS_SECONDS=25
```

### 3. Run Animal Crossing in Dolphin
- Download Dolphin emulator
- Load Animal Crossing (GAFE01) ROM
- **⚠️ IMPORTANT**: Start the game and wait until you're past the loading screen and in the actual game world
- Get to a conversation with a villager

### 4. Launch the Mod
```bash
# Watch mode - continuously generates dialogue
python ac_parser_encoder.py --watch

# One-shot mode - generate once
python ac_parser_encoder.py --write
```

## 🎮 How It Works

1. **Memory Reading**: Connects to Dolphin's memory to read current dialogue
2. **Context Analysis**: Captures screenshots and analyzes conversation context
3. **AI Generation**: Uses LLM to create natural, contextual responses
4. **Memory Writing**: Encodes and writes new dialogue back to the game
5. **Real-time Updates**: Continuously monitors and updates conversations

## 🔧 Advanced Usage

### Watch Mode (Recommended for YouTube)
```bash
# Continuous monitoring with custom settings
python ac_parser_encoder.py --watch --interval 0.1 --size 512 --print-all
```

### Custom Addresses
```bash
# Monitor multiple dialogue addresses
python ac_parser_encoder.py --watch --addresses 0x81298360 0x81298380
```

### Debug Mode
```bash
# See raw hex data
python ac_parser_encoder.py --dump
```

## 🌟 Features

- **Smart Dialogue Generation**: Context-aware responses based on game state
- **Real-time Updates**: Continuous monitoring and generation
- **Screenshot Integration**: Visual context for better AI responses
- **Gossip System**: Villagers remember and reference past conversations
- **Multi-LLM Support**: Google Gemini, OpenAI and Anthropic Claude compatibility
- **Memory Safety**: Prevents overwriting during active conversations

## 🎯 Perfect for YouTube Content

- **Interactive Streams**: Let viewers suggest conversation topics
- **AI Villager Showcases**: Demonstrate different personality types
- **Modding Tutorials**: Show how to create custom game experiences
- **AI Gaming Content**: Explore the future of AI-powered games

## 🛠️ Technical Details

- **Memory Engine**: Uses dolphin-memory-engine for GameCube memory access
- **Text Encoding**: Full Animal Crossing character set and control code support
- **LLM Integration**: Modular design supporting multiple AI providers
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Running the tests**: `python -m unittest discover -s tests -t . -v` (no Dolphin or API key needed)

## 🚨 Important Notes

- **Emulator Only**: This mod works with Dolphin emulator, not original hardware
- **Memory Addresses**: May need adjustment for different game versions
- **API Costs**: OpenAI usage incurs charges, Google Gemini has free tier, Anthropic Claude (claude-haiku-5-5) is paid, priced per token
- **Game Compatibility**: Tested with Animal Crossing (GAFE01) version

## ⚠️ Known Issues & Limitations

- **🪲 Some Obvious Bugs**: This is a work-in-progress mod with known issues
- **🖥️ Platform Testing**: Only tested on macOS - Windows/Linux may have compatibility issues
- **🎮 Timing Critical**: Must start the mod AFTER entering the game world (past loading screen)
- **💾 Memory Stability**: May occasionally crash or behave unexpectedly
- **🔧 Experimental**: This is experimental software - use at your own risk!

## 🐛 Bug Reports & Contributions

**PRs are welcome!** This mod needs help from the community to improve:
- Fix platform compatibility issues
- Resolve known bugs and crashes
- Improve memory reading stability
- Add new features and LLM providers
- Test on different game versions and platforms

Found a bug? Want to help? Open an issue or submit a pull request!

## 🤝 Contributing

Found a bug? Want to add features? **Contributions are very welcome!** This mod needs community help to become stable.

**Most Needed:**
- 🐛 **Bug Fixes**: Fix crashes, memory issues, and platform compatibility
- 🖥️ **Platform Support**: Test and fix Windows/Linux compatibility issues
- 🎮 **Game Versions**: Test with different Animal Crossing versions
- 📱 **UI Improvements**: Better error handling and user feedback
- 🧪 **Testing**: Help test on different systems and configurations

**How to Help:**
- Report issues with detailed error messages and system info
- Test on different platforms (Windows, Linux, different macOS versions)
- Submit pull requests with fixes and improvements
- Help improve documentation and setup instructions

---

**Ready to bring your Animal Crossing villagers to life with AI?** 🎮✨
# voice/ package -- contains speech recognition logic:
#   speech.py  -> listen() function + VoiceController class
#
# Audio stack:  sounddevice (mic capture) + scipy (WAV I/O)
#               + SpeechRecognition (Google Web Speech API)
#
# NOTE: This module does NOT depend on PyAudio.

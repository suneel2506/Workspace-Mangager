"""
============================================================
  speech.py -- Voice Command Recognition Module
============================================================

PURPOSE:
    Listens to the microphone, transcribes speech to text using
    Google's free Web Speech API, and extracts a workspace name
    from phrases like:

        "Open coding workspace"
        "Launch embedded"
        "Start vlsi workspace"

DEPENDENCIES (PyAudio-FREE):
    pip install SpeechRecognition sounddevice scipy

    - SpeechRecognition -- provides the ``Recognizer`` class and
      the Google Web Speech API wrapper.
    - sounddevice      -- records raw audio from the microphone
      via PortAudio.  Unlike PyAudio, sounddevice ships with
      pre-built PortAudio binaries on Windows/macOS/Linux and
      installs cleanly on Python 3.12 - 3.14.
    - scipy            -- writes the recorded NumPy array to a
      temporary WAV file that SpeechRecognition can read.

WHY NOT PyAudio?
    PyAudio wraps PortAudio via a C extension that must be
    compiled at install time.  On Python 3.13+ the build
    regularly fails because the upstream PortAudio headers
    are not updated for the new stable ABI.  ``sounddevice``
    bundles PortAudio as a shared library, so no compiler is
    needed.

HOW IT WORKS:
    1. Record a fixed-duration audio clip with ``sounddevice``.
    2. Save the clip as a temporary WAV file with ``scipy.io``.
    3. Feed the WAV file to ``SpeechRecognition``'s recognizer.
    4. Transcribe with the Google Web Speech API.
    5. Parse the returned text for a known workspace name.

FUTURE HOOKS:
    - Continuous listening mode (wake-word detection).
    - Offline recognition via Vosk / Whisper.
    - Confirmations: "Did you mean 'coding'?"
    - Multi-language support.
    - Voice activity detection (VAD) to auto-stop recording.
============================================================
"""

import os
import tempfile
from typing import Optional

from core.logger import Logger

# ── Optional dependency imports ────────────────────────────
# The rest of the project (CLI + interactive menu) works even
# if these are not installed.  We check at runtime and give a
# clear message instead of crashing.

try:
    import speech_recognition as sr  # type: ignore[import-untyped]
    SR_AVAILABLE: bool = True
except ImportError:
    SR_AVAILABLE = False

try:
    import sounddevice as sd   # type: ignore[import-untyped]
    import numpy as np         # installed automatically with sounddevice
    SD_AVAILABLE: bool = True
except ImportError:
    SD_AVAILABLE = False

try:
    from scipy.io import wavfile  # type: ignore[import-untyped]
    SCIPY_AVAILABLE: bool = True
except ImportError:
    SCIPY_AVAILABLE = False


# ── Recording defaults ─────────────────────────────────────
DEFAULT_SAMPLE_RATE: int = 16000   # 16 kHz — standard for speech
DEFAULT_DURATION: float = 5.0      # seconds to record
DEFAULT_CHANNELS: int = 1          # mono


# ============================================================
#  Reusable ``listen()`` function
# ============================================================

def listen(
    duration: float = DEFAULT_DURATION,
    sample_rate: int = DEFAULT_SAMPLE_RATE,
) -> Optional[str]:
    """
    Record audio from the microphone, convert speech to text,
    and return the recognized text string.

    This is a **standalone, reusable function** — you can call it
    from anywhere in the project (or from other projects) without
    instantiating any class.

    Pipeline
    --------
    1. ``sounddevice.rec()``  -- capture raw audio as a NumPy array.
    2. ``scipy.io.wavfile``   -- write the array to a temporary WAV.
    3. ``sr.Recognizer``      -- read the WAV and call Google's API.

    Parameters
    ----------
    duration : float
        How many seconds to record.  Default is 5.
    sample_rate : int
        Audio sample rate in Hz.  Default is 16 000 (16 kHz).

    Returns
    -------
    str or None
        The recognized text, or ``None`` if recognition failed.

    Error Handling
    --------------
    - **No microphone**      -- catches ``sounddevice.PortAudioError``
      and ``OSError``.
    - **No speech detected** -- catches ``sr.UnknownValueError``.
    - **No internet**        -- catches ``sr.RequestError``.
    - **Permission denied**  -- catches ``PermissionError`` (e.g.
      microphone blocked by OS privacy settings).
    """
    # ── Guard: check that all dependencies are installed ────
    if not SR_AVAILABLE:
        print(
            "\n  [x] SpeechRecognition is not installed.\n"
            "      Run:  pip install SpeechRecognition\n"
        )
        return None

    if not SD_AVAILABLE:
        print(
            "\n  [x] sounddevice is not installed.\n"
            "      Run:  pip install sounddevice\n"
        )
        return None

    if not SCIPY_AVAILABLE:
        print(
            "\n  [x] scipy is not installed.\n"
            "      Run:  pip install scipy\n"
        )
        return None

    # ── Step 1: Record audio with sounddevice ──────────────
    try:
        print(f"  ...  Recording for {duration:.0f} seconds. Speak now!")
        audio_data: np.ndarray = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=DEFAULT_CHANNELS,
            dtype="int16",           # 16-bit PCM — WAV standard
        )
        sd.wait()  # Block until recording is finished.

    except PermissionError:
        print("  [x] Microphone access denied.")
        print("      Check your OS privacy settings (Settings > Privacy > Microphone).")
        return None

    except sd.PortAudioError as exc:
        print(f"  [x] Audio device error: {exc}")
        print("      Make sure a microphone is connected.")
        return None

    except OSError as exc:
        print(f"  [x] Microphone error: {exc}")
        print("      Make sure a microphone is connected and not in use.")
        return None

    # ── Step 2: Save to a temporary WAV file ───────────────
    # We use a temp file so there's no leftover clutter.
    # The file is deleted in the ``finally`` block below.
    tmp_path: str = ""
    try:
        # Create a named temp file that we'll write to and then
        # hand off to SpeechRecognition.
        fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)  # Close the OS-level file descriptor.

        wavfile.write(tmp_path, sample_rate, audio_data)

        # ── Step 3: Transcribe with SpeechRecognition ──────
        recognizer = sr.Recognizer()

        with sr.AudioFile(tmp_path) as source:
            audio = recognizer.record(source)

        # ── Step 4: Call Google Web Speech API ─────────────
        text: str = recognizer.recognize_google(audio)  # type: ignore[arg-type]
        return text

    except sr.UnknownValueError:
        # Google could not understand the audio.
        print("  [!] Could not understand audio. Please try again.")
        return None

    except sr.RequestError as exc:
        # Network or API error.
        print(f"  [x] Google Speech API error: {exc}")
        print("      Check your internet connection.")
        return None

    except PermissionError:
        print("  [x] Permission denied while writing temp audio file.")
        return None

    except Exception as exc:
        # Catch-all for unexpected errors.
        print(f"  [x] Unexpected error during transcription: {exc}")
        return None

    finally:
        # ── Cleanup: delete the temporary WAV file ─────────
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass  # Non-critical — temp dir will clean up eventually.


# ============================================================
#  VoiceController class
# ============================================================

class VoiceController:
    """
    Captures a voice command and extracts a workspace name.

    Uses the standalone ``listen()`` function internally, so all
    microphone access goes through ``sounddevice`` — no PyAudio.

    Attributes
    ----------
    workspace_names : list[str]
        Known workspace names to match against.
    logger : Logger
        Logger instance for recording voice events.
    duration : float
        How many seconds to record per attempt.

    Usage
    -----
        vc = VoiceController(["coding", "embedded", "vlsi"])
        name = vc.listen_for_workspace()
        if name:
            launcher.launch(name, items)
    """

    # Words the user might say before the workspace name.
    _TRIGGER_WORDS: list[str] = ["open", "launch", "start", "load", "run"]

    def __init__(
        self,
        workspace_names: list[str],
        logger: Logger | None = None,
        duration: float = DEFAULT_DURATION,
    ) -> None:
        """
        Parameters
        ----------
        workspace_names : list[str]
            All workspace names currently defined in the config.
        logger : Logger, optional
            If omitted, a default Logger is created.
        duration : float, optional
            Seconds to record per listen attempt.  Default 5.
        """
        self.workspace_names: list[str] = [
            name.lower() for name in workspace_names
        ]
        self.logger: Logger = logger or Logger()
        self.duration: float = duration

    # ── Public API ─────────────────────────────────────────
    def listen_for_workspace(self) -> Optional[str]:
        """
        Listen to the microphone once and try to match a
        workspace name.

        Returns
        -------
        str or None
            The matched workspace name, or ``None`` if nothing
            was recognized or no workspace matched.
        """
        # Check dependencies before attempting to record.
        if not (SR_AVAILABLE and SD_AVAILABLE and SCIPY_AVAILABLE):
            missing: list[str] = []
            if not SR_AVAILABLE:
                missing.append("SpeechRecognition")
            if not SD_AVAILABLE:
                missing.append("sounddevice")
            if not SCIPY_AVAILABLE:
                missing.append("scipy")
            print(
                f"\n  [x] Missing dependencies: {', '.join(missing)}\n"
                f"      Run:  pip install {' '.join(missing)}\n"
            )
            self.logger.log_voice_event(
                f"Missing dependencies: {', '.join(missing)}"
            )
            return None

        print("\n  [mic] Listening... Say something like: 'Open coding workspace'")

        # Delegate to the reusable listen() function.
        text: Optional[str] = listen(duration=self.duration)

        if text is None:
            # listen() already printed the specific error message.
            self.logger.log_voice_event("Recognition failed (no text returned)")
            return None

        print(f"  [>] You said: \"{text}\"")
        self.logger.log_voice_event(f"Recognized: \"{text}\"")

        # Extract workspace name from the transcribed text.
        workspace: Optional[str] = self._extract_workspace(text)

        if workspace:
            print(f"  [+] Matched workspace: {workspace}")
            return workspace
        else:
            print("  [!] Could not match a workspace name.")
            print(f"      Available: {', '.join(self.workspace_names)}")
            self.logger.log_voice_event(
                f"No workspace matched in: \"{text}\""
            )
            return None

    # ── Private helpers ────────────────────────────────────
    def _extract_workspace(self, text: str) -> Optional[str]:
        """
        Parse transcribed text and find a known workspace name.

        Strategy:
            1. Tokenize the text into lowercase words.
            2. Look for any word that matches a workspace name.
            3. Prefer words that come after a trigger word
               ("open", "launch", etc.) but accept bare matches too.

        Parameters
        ----------
        text : str
            The full transcribed sentence.

        Returns
        -------
        str or None
            The matched workspace name, or ``None``.
        """
        words: list[str] = text.lower().split()

        # First pass -- look for a workspace name right after a trigger.
        for i, word in enumerate(words):
            if word in self._TRIGGER_WORDS and i + 1 < len(words):
                candidate: str = words[i + 1]
                if candidate in self.workspace_names:
                    return candidate

        # Second pass -- any word that IS a workspace name.
        for word in words:
            if word in self.workspace_names:
                return word

        return None

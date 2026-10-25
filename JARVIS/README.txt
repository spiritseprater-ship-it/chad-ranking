================================================================================
                        JARVIS  -  Windows AI assistant
================================================================================

WHAT THIS IS
------------
JARVIS is a voice-controlled Windows 11 assistant. Say "Hey Jarvis" and ask it
to open apps, find files, search the web, read a document, run multi-step
tasks, or just chat. It answers in English, Hindi or Hinglish.

The AI brain is Google Gemini. Your PC does the listening, the speaking and the
desktop control locally.


QUICK START
-----------
1. Extract this zip anywhere (for example C:\Program Files\JARVIS).
2. Double-click JARVIS.exe.
3. The first-run wizard asks for three things:
     - your microphone (say "Hey JARVIS" to test it)
     - your Gemini API key  (free, from https://aistudio.google.com/app/apikey)
     - whether to launch at Windows startup
   The key is stored in %USERPROFILE%\.jarvis\gemini_key.txt with restricted
   permissions. It is never written to config.json and never logged.
4. Say "Hey Jarvis" and try:  "open Chrome", "find my budget file",
   "search the web for flights to Mumbai", "what is the exchange rate".

NO PYTHON NEEDED - this is a packaged application. Do not delete the JARVIS
folder next to the executable; it contains the runtime.


CONTROLS
--------
  "Hey Jarvis"                      wake it up
  "Jarvis, cancel" / "cancel"      stop the current task
  "Check my JARVIS"                run a self-diagnostic
  "Show task history"              what it has done recently
  "Turn on low resource mode"      fewer particles, lower CPU
  Ctrl + Alt + J                    emergency stop (works offline)


WHAT IT CAN DO
--------------
  * open applications and files, search your files by name
  * browser automation: open pages, search, read a page, open a result
  * window management: list, focus, minimise, maximise, close
  * mouse and keyboard control (always with confirmation)
  * read text documents and summarise web pages with Gemini
  * multi-step tasks: "search for flights, open the third result and tell me
    the price"
  * optional webcam photos (enabled in Settings, never streaming)


OPTIONAL: BROWSER AUTOMATION
----------------------------
Browser automation is switched off by default because its Chromium download is
about 150 MB. To use it, run this once on the PC (after installing the
optional requirements):

    playwright install chromium

Then enable "browser automation" in Settings.


OPTIONAL: CAMERA
-----------------
Camera capture is off by default. Enable it in Settings and grant the Windows
camera permission. JARVIS only takes a photo when you ask for one.


UPGRADE / REINSTALL
-------------------
Replace the JARVIS folder with the new one. Your API key and history live in
%USERPROFILE%\.jarvis and %LOCALAPPDATA%\JARVIS, so they survive a reinstall.


UNINSTALL
---------
Double-click "JARVIS (uninstall).lnk", or run:

    powershell -ExecutionPolicy Bypass -File uninstall.ps1 -AppDir "C:\Program Files\JARVIS"

Add -Purge to also delete your history, screenshots, photos and stored key.


TROUBLESHOOTING
---------------
  * "Gemini is not configured"       add the API key in Settings.
  * "no microphone was found"        check Windows Sound settings.
  * "Playwright is not installed"    run "playwright install chromium".
  * Wake word not detected           enable it in Settings, or use the Start
                                      listening button / click the orb.
  * Nothing works                    run "JARVIS --check" (or the Check my
                                      JARVIS command) for a diagnostic report.

Support and source: see README.md next to this file.

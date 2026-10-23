# UI is a local web page shown in an Edge app window

The UI is plain HTML/JS (no framework, no build step) served by the program's own Python HTTP server on `127.0.0.1` and opened with `msedge --app=http://127.0.0.1:<port>`, so it looks like an ordinary window. We chose this over a native PySide6 window even though 100–200 MB for Qt was acceptable: the deciding factor is that the developer (an AI agent) can open and check the very same page in its own built-in browser, which a Qt window does not allow, and the web stack is already proven on the target laptops in the prototype.

## Considered Options

- **PySide6**: one process, no browser quirks (F5, Ctrl+W, zoom), no dependency on Edge or its group policies, less RAM on the 3.8 GB Celeron. Rejected for the reason above; it was also never tested in embeddable Python.
- **pywebview (WebView2)**: a native window with HTML inside and no server, but it needs pythonnet, untested in embeddable Python.
- **tkinter**: not included in embeddable Python.

## Consequences

- The page is only a view: all state (the Library, synthesis progress, playback position) lives in the Python process, so a reload (F5) or a reopened window picks up where it was.
- The program has to handle its own lifecycle: shut down when the window is closed, and a second launch has to open the already-running instance rather than start another server.
- The core (Library, synthesis, Voice providers) stays independent of the UI, so the UI could still be replaced later.

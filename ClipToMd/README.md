# ClipToMd for Windows

**ClipToMd** is a lightweight Windows system tray utility that processes your clipboard content. It effectively converts rich HTML content (like code copied from **VS Code**, **Cursor**, or generic web pages) into clean, plain-text **Markdown**, ready for pasting into documentation, issue trackers, or chat apps.

## Features

*   **Smart Auto-Conversion**: 
    *   **VS Code / Cursor (Default)**: Automatically detects and converts content copied from code editors like VS Code or Cursor or Antigravity (stripping local `vscode-file://` links while keeping text).
    *   **All HTML (Optional)**: Can be toggled to automatically convert *any* HTML content copied to the clipboard.
*   **Global Hotkey**: Press `Ctrl` + `Shift` + `M` (customizable) to **Toggle Active/Inactive** state.
*   **Clean Output**: Uses [ReverseMarkdown](https://github.com/mysticmind/reversemarkdown-net) to produce high-quality GitHub Flavored Markdown.
*   **System Tray App**: Runs silently in the background.
    *   **Info Bubbles**: Provides unobtrusive notifications upon successful conversion.
    *   **Double-click** the tray icon to toggle the tool Active/Inactive.

## Prerequisites

*   [.NET Desktop Runtime](https://dotnet.microsoft.com/download/dotnet) (Version 9.0 or later recommended).
*   Windows OS.

## Installation & Build

1.  Clone the repository:
    ```bash
    git clone https://github.com/pjanec/ClipToMd.git
    cd ClipToMd
    ```

2.  Build the project:
    ```powershell
    dotnet build -c Release
    ```

3.  Run the executable:
    ```powershell
    .\bin\Release\net9.0-windows\ClipToMd.exe
    ```

## Usage

1.  **Run** the application. You will see a small gray "M" icon in your system tray (starts Inactive).
2.  **Double-click** the tray icon to Activate it (turns Blue).
2.  **Right-click** the tray icon to configure auto-conversion modes:
    *   **Auto: VS Code Only** (Checked by default): Automatically converts when you copy from VS Code.
    *   **Auto: All HTML** (Unchecked by default): Automatically converts any HTML content found in the clipboard.
3.  **Copy** something!
    *   If Auto-mode matches, you'll see a small "Auto-Converted" bubble.
    *   Otherwise, press `Ctrl` + `Shift` + `M` to toggle the tool Active/Inactive.
4.  **Paste** (`Ctrl` + `V`) your perfectly formatted Markdown.

## License

[MIT](LICENSE)

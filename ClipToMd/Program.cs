using ReverseMarkdown;
using ReverseMarkdown.Converters;
using System;
using System.Drawing;
using System.IO;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Windows.Forms;

namespace VsCodeToMd
{
    static class Program
    {
        [STAThread]
        static void Main()
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            
            // Start the application without a visible form, just the tray icon
            Application.Run(new SysTrayAppContext());
        }
    }

    public class AppSettings
    {
        public int HotkeyKey { get; set; } = (int)Keys.M;
        public int HotkeyModifiers { get; set; } = (int)(KeyModifiers.Control | KeyModifiers.Shift);
        public bool AutoConvertVsCode { get; set; } = true;
        public bool AutoConvertAny { get; set; } = false;
        public bool RemoveBackslashes { get; set; } = true;
        public bool DecodeHtmlEntities { get; set; } = true;
    }

    public class SysTrayAppContext : ApplicationContext
    {
        private NotifyIcon _notifyIcon;
        private ContextMenuStrip _contextMenu;
        private GlobalHotkey _hotkey;
        private bool _isActive = false;
        private ConfigForm _configForm;

        private ClipboardMonitor _clipboardMonitor;
        private AppSettings _settings;
        private string _settingsPath;

        public SysTrayAppContext()
        {
            LoadSettings();
            InitializeContext();
            RegisterHotKey();
            InitializeClipboardMonitor();
        }

        private void LoadSettings()
        {
            try
            {
                string appData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ClipToMd");
                Directory.CreateDirectory(appData);
                _settingsPath = Path.Combine(appData, "settings.json");

                if (File.Exists(_settingsPath))
                {
                    string json = File.ReadAllText(_settingsPath);
                    _settings = JsonSerializer.Deserialize<AppSettings>(json) ?? new AppSettings();
                }
                else
                {
                    _settings = new AppSettings();
                }
            }
            catch
            {
                _settings = new AppSettings();
            }
        }

        private void SaveSettings()
        {
            try
            {
                string json = JsonSerializer.Serialize(_settings);
                File.WriteAllText(_settingsPath, json);
            }
            catch (Exception ex)
            {
                _notifyIcon.ShowBalloonTip(3000, "Error", "Failed to save settings: " + ex.Message, ToolTipIcon.Error);
            }
        }

        private void InitializeContext()
        {
            // Create Context Menu
            _contextMenu = new ContextMenuStrip();
            ((ToolStripMenuItem)_contextMenu.Items.Add("Active", null, ToggleActive)).Checked = false;
            ((ToolStripMenuItem)_contextMenu.Items.Add("Auto: VS Code Only", null, ToggleAutoConvertVsCode)).Checked = _settings.AutoConvertVsCode;
            ((ToolStripMenuItem)_contextMenu.Items.Add("Auto: All HTML", null, ToggleAutoConvertAny)).Checked = _settings.AutoConvertAny;
            ((ToolStripMenuItem)_contextMenu.Items.Add("Remove Backslashes", null, ToggleRemoveBackslashes)).Checked = _settings.RemoveBackslashes;
            ((ToolStripMenuItem)_contextMenu.Items.Add("Decode HTML Entities", null, ToggleDecodeHtmlEntities)).Checked = _settings.DecodeHtmlEntities;
            _contextMenu.Items.Add(new ToolStripSeparator());
            _contextMenu.Items.Add("Set Hotkey...", null, ShowConfig);
            _contextMenu.Items.Add("Exit", null, Exit);

            // Create Tray Icon (Drawing one programmatically to avoid external .ico files)
            _notifyIcon = new NotifyIcon();
            // Icon and Text will be set by SetActiveState
            _notifyIcon.ContextMenuStrip = _contextMenu;
            _notifyIcon.Visible = true;
            _notifyIcon.DoubleClick += ToggleActive;

            // Set initial state
            SetActiveState(false);
        }

        private void InitializeClipboardMonitor()
        {
            _clipboardMonitor = new ClipboardMonitor();
            _clipboardMonitor.ClipboardChanged += OnClipboardChanged;
        }

        private void OnClipboardChanged(object sender, EventArgs e)
        {
            if (!_isActive) return;
            if (!_settings.AutoConvertVsCode && !_settings.AutoConvertAny) return;
            
            // Only proceed if it looks like HTML
            if (!Clipboard.ContainsText(TextDataFormat.Html)) return;

            try 
            {
                string rawHtml = Clipboard.GetText(TextDataFormat.Html);
                bool shouldConvert = false;
                
                if (_settings.AutoConvertAny)
                {
                    shouldConvert = true;
                }
                else if (_settings.AutoConvertVsCode)
                {
                    // Check specifically for VS Code signature
                    // Relaxed check to catch Cursor and potential variants
                    if (rawHtml.IndexOf("SourceURL:vscode-file://", StringComparison.OrdinalIgnoreCase) >= 0)
                    {
                        shouldConvert = true;
                    }
                }

                if (shouldConvert)
                {
                    ProcessClipboard(isAuto: true, preLoadedHtml: rawHtml);
                }
            }
            catch (Exception) 
            { 
                // Swallow clipboard access errors (locking issues etc)
            }
        }

        private void RegisterHotKey()
        {
            if (_hotkey != null) _hotkey.Dispose();
            
            _hotkey = new GlobalHotkey();
            try
            {
                _hotkey.Register((KeyModifiers)_settings.HotkeyModifiers, (Keys)_settings.HotkeyKey);
                _hotkey.KeyPressed += OnHotkeyPressed;
            }
            catch (Exception ex)
            {
                _notifyIcon.ShowBalloonTip(3000, "Error", "Could not register hotkey: " + ex.Message, ToolTipIcon.Error);
            }
        }

        private void OnHotkeyPressed(object sender, EventArgs e)
        {
            // Toggle Active State
            ToggleActive(sender, e);
            
            // Show notification bubble
            string state = _isActive ? "Activated" : "Deactivated";
            _notifyIcon.ShowBalloonTip(1000, "ClipToMd", $"Tool is now {state}", ToolTipIcon.Info);
        }

        private void ProcessClipboard(bool isAuto, string preLoadedHtml = null)
        {
            // VS Code copies data as "HTML Format"
            if (!Clipboard.ContainsText(TextDataFormat.Html) && preLoadedHtml == null)
            {
                if (!isAuto) 
                    _notifyIcon.ShowBalloonTip(1000, "Info", "No HTML found in clipboard.", ToolTipIcon.Warning);
                return;
            }

            // 1. Get Raw HTML
            string rawClipboardHtml = preLoadedHtml ?? Clipboard.GetText(TextDataFormat.Html);

            // 2. Extract the Fragment (The actual content between headers)
            string cleanHtml = ExtractFragment(rawClipboardHtml);

            if (string.IsNullOrWhiteSpace(cleanHtml)) return;

            // 2.1 Remove VS Code specific links (keep text content)
            cleanHtml = RemoveVsCodeLinks(cleanHtml);

            // 3. Convert to Markdown using ReverseMarkdown
            var config = new ReverseMarkdown.Config
            {
                UnknownTags = Config.UnknownTagsOption.Drop, // Remove unmapped tags (like VS Code widgets)
                GithubFlavored = true, // Tables, etc.
                RemoveComments = true,
                SmartHrefHandling = true
            };

            var converter = new ReverseMarkdown.Converter(config);
            string markdown = converter.Convert(cleanHtml);

            // 4.1 Decode HTML entities if enabled (e.g., &gt; -> >, &amp; -> &)
            if (_settings.DecodeHtmlEntities)
            {
                markdown = WebUtility.HtmlDecode(markdown);
            }

            // 4.2 Remove unnecessary backslashes if enabled
            if (_settings.RemoveBackslashes)
            {
                markdown = RemoveUnnecessaryBackslashes(markdown);
            }

            // 4. Place back on Clipboard
            try
            {
                Clipboard.SetText(markdown);
                
                // Visual confirmation
                _notifyIcon.Icon = GenerateIcon(Color.LimeGreen);
                string title = isAuto ? "Auto-Converted" : "Success";
                string msg = isAuto ? "VS Code HTML detected and converted." : "Converted to Markdown";
                _notifyIcon.ShowBalloonTip(500, title, msg, ToolTipIcon.Info);
                
                var t = new System.Windows.Forms.Timer { Interval = 500 };
                t.Tick += (s, e) => { _notifyIcon.Icon = GenerateIcon(_isActive ? Color.DodgerBlue : Color.Gray); t.Stop(); };
                t.Start();
            }
            catch (Exception ex)
            {
                if (!isAuto)
                    _notifyIcon.ShowBalloonTip(3000, "Error", "Failed to set clipboard: " + ex.Message, ToolTipIcon.Error);
            }
        }

        private string RemoveUnnecessaryBackslashes(string markdown)
        {
            if (string.IsNullOrEmpty(markdown))
                return markdown;

            // Remove backslashes preceding these characters: ( ) [ ] < > + -
            // Only remove if the backslash is not already escaped (not preceded by another backslash)
            return Regex.Replace(markdown, @"(?<!\\)\\([(){}\[\]<>+\-_@#$%\^\*])", "$1", RegexOptions.Multiline);
        }

        private string RemoveVsCodeLinks(string html)
        {
            if (string.IsNullOrEmpty(html))
                return html;

            // 1) Remove <img ... src="vscode-file://..."> (self-closing or not)
            html = Regex.Replace(
                html,
                @"<img\b[^>]*\bsrc\s*=\s*[""']vscode-file://[^""']*[""'][^>]*\/?>",
                string.Empty,
                RegexOptions.IgnoreCase | RegexOptions.Singleline);

            // 2) Replace <a ... href="vscode-file://...">INNER</a> with INNER
            html = Regex.Replace(
                html,
                @"<a\s+[^>]*\bhref\s*=\s*[""']vscode-file://[^""']*[""'][^>]*>(.*?)</a>",
                "$1",
                RegexOptions.IgnoreCase | RegexOptions.Singleline);

            // 3) Remove Markdown-style images referencing vscode-file:// e.g. ![](vscode-file://...)
            html = Regex.Replace(
                html,
                @"!\[.*?\]\(\s*vscode-file://[^)]*\)",
                string.Empty,
                RegexOptions.IgnoreCase | RegexOptions.Singleline);

            return html;
        }

        private string ExtractFragment(string rawHtml)
        {
            string startMarker = "<!--StartFragment-->";
            string endMarker = "<!--EndFragment-->";

            int start = rawHtml.IndexOf(startMarker);
            int end = rawHtml.IndexOf(endMarker);

            if (start != -1 && end != -1)
            {
                start += startMarker.Length;
                return rawHtml.Substring(start, end - start);
            }

            return rawHtml;
        }

        private void SetActiveState(bool active)
        {
            _isActive = active;
            ((ToolStripMenuItem)_contextMenu.Items[0]).Checked = _isActive;
            _notifyIcon.Icon = GenerateIcon(_isActive ? Color.DodgerBlue : Color.Gray);
            _notifyIcon.Text = _isActive ? $"Active ({GetHotkeyString()})" : "Inactive";
        }

        private void ToggleActive(object sender, EventArgs e)
        {
            SetActiveState(!_isActive);
        }

        private void ToggleAutoConvertVsCode(object sender, EventArgs e)
        {
            _settings.AutoConvertVsCode = !_settings.AutoConvertVsCode;
            ((ToolStripMenuItem)_contextMenu.Items[1]).Checked = _settings.AutoConvertVsCode;
            SaveSettings();
        }

        private void ToggleAutoConvertAny(object sender, EventArgs e)
        {
            _settings.AutoConvertAny = !_settings.AutoConvertAny;
            ((ToolStripMenuItem)_contextMenu.Items[2]).Checked = _settings.AutoConvertAny;
            SaveSettings();
        }

        private void ToggleRemoveBackslashes(object sender, EventArgs e)
        {
            _settings.RemoveBackslashes = !_settings.RemoveBackslashes;
            ((ToolStripMenuItem)_contextMenu.Items[3]).Checked = _settings.RemoveBackslashes;
            SaveSettings();
        }

        private void ToggleDecodeHtmlEntities(object sender, EventArgs e)
        {
            _settings.DecodeHtmlEntities = !_settings.DecodeHtmlEntities;
            ((ToolStripMenuItem)_contextMenu.Items[4]).Checked = _settings.DecodeHtmlEntities;
            SaveSettings();
        }

        private string GetHotkeyString()
        {
            return $"{(KeyModifiers)_settings.HotkeyModifiers} + {(Keys)_settings.HotkeyKey}";
        }

        private void ShowConfig(object sender, EventArgs e)
        {
            if (_configForm == null || _configForm.IsDisposed)
            {
                _configForm = new ConfigForm((Keys)_settings.HotkeyKey, (KeyModifiers)_settings.HotkeyModifiers);
                if (_configForm.ShowDialog() == DialogResult.OK)
                {
                    _settings.HotkeyKey = (int)_configForm.SelectedKey;
                    _settings.HotkeyModifiers = (int)_configForm.SelectedModifiers;
                    SaveSettings();
                    RegisterHotKey();
                    
                    // Update tooltip if active
                    if (_isActive)
                        _notifyIcon.Text = $"Active ({GetHotkeyString()})";
                }
            }
        }

        private void Exit(object sender, EventArgs e)
        {
            _notifyIcon.Visible = false;
            _hotkey.Dispose();
            _clipboardMonitor.Dispose();
            Application.Exit();
        }

        private Icon GenerateIcon(Color color)
        {
            Bitmap bmp = new Bitmap(16, 16);
            using (Graphics g = Graphics.FromImage(bmp))
            {
                g.Clear(Color.Transparent);
                using (Brush b = new SolidBrush(color))
                {
                    g.FillEllipse(b, 2, 2, 12, 12);
                }
                g.DrawString("M", new Font("Arial", 8, FontStyle.Bold), Brushes.White, 2, 1);
            }
            return Icon.FromHandle(bmp.GetHicon());
        }
    }

    // --- CLIPBOARD MONITOR ---
    public class ClipboardMonitor : NativeWindow, IDisposable
    {
        private const int WM_CLIPBOARDUPDATE = 0x031D;

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool AddClipboardFormatListener(IntPtr hwnd);

        [DllImport("user32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool RemoveClipboardFormatListener(IntPtr hwnd);

        public event EventHandler ClipboardChanged;

        public ClipboardMonitor()
        {
            CreateHandle(new CreateParams());
            AddClipboardFormatListener(Handle);
        }

        protected override void WndProc(ref Message m)
        {
            if (m.Msg == WM_CLIPBOARDUPDATE)
            {
                ClipboardChanged?.Invoke(this, EventArgs.Empty);
            }
            base.WndProc(ref m);
        }

        public void Dispose()
        {
            RemoveClipboardFormatListener(Handle);
            DestroyHandle();
        }
    }

    // --- HOTKEY LOGIC ---
    public class GlobalHotkey : IDisposable
    {
        private NativeWindow _window = new NativeWindow();
        private int _id;

        [DllImport("user32.dll")]
        private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

        [DllImport("user32.dll")]
        private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

        public event EventHandler KeyPressed;

        public GlobalHotkey()
        {
            _window.CreateHandle(new CreateParams());
            _id = _window.Handle.ToInt32(); // Unique ID based on handle
        }

        public void Register(KeyModifiers modifier, Keys key)
        {
            if (!RegisterHotKey(_window.Handle, _id, (uint)modifier, (uint)key))
                throw new InvalidOperationException("Could not register hotkey. It might be in use.");
            
            // Hook the message loop
            Application.AddMessageFilter(new MessageFilter(_window.Handle, () => KeyPressed?.Invoke(this, EventArgs.Empty)));
        }

        public void Dispose()
        {
            UnregisterHotKey(_window.Handle, _id);
            _window.DestroyHandle();
        }

        private class MessageFilter : IMessageFilter
        {
            private readonly IntPtr _hwnd;
            private readonly Action _action;

            public MessageFilter(IntPtr hwnd, Action action)
            {
                _hwnd = hwnd;
                _action = action;
            }

            public bool PreFilterMessage(ref Message m)
            {
                if (m.Msg == 0x0312 && m.HWnd == _hwnd) // WM_HOTKEY
                {
                    _action();
                    return true;
                }
                return false;
            }
        }
    }

    [Flags]
    public enum KeyModifiers
    {
        Alt = 1, Control = 2, Shift = 4, Win = 8
    }

    // --- CONFIG UI ---
    public class ConfigForm : Form
    {
        private Label _lblInfo;
        public Keys SelectedKey { get; private set; }
        public KeyModifiers SelectedModifiers { get; private set; }

        public ConfigForm(Keys currentKey, KeyModifiers currentModifiers)
        {
            SelectedKey = currentKey;
            SelectedModifiers = currentModifiers;

            this.Size = new Size(300, 150);
            this.Text = "Set Hotkey";
            this.StartPosition = FormStartPosition.CenterScreen;
            this.FormBorderStyle = FormBorderStyle.FixedToolWindow;
            this.KeyPreview = true;

            _lblInfo = new Label { 
                Text = $"Press any key combination...\n\nCurrent: {SelectedModifiers} + {SelectedKey}", 
                Dock = DockStyle.Fill, 
                TextAlign = ContentAlignment.MiddleCenter,
                Font = new Font("Segoe UI", 10)
            };
            this.Controls.Add(_lblInfo);
            
            Button btnOk = new Button { Text = "OK", DialogResult = DialogResult.OK, Dock = DockStyle.Bottom };
            this.Controls.Add(btnOk);
        }

        protected override void OnKeyDown(KeyEventArgs e)
        {
            if (e.KeyCode == Keys.ControlKey || e.KeyCode == Keys.ShiftKey || e.KeyCode == Keys.Menu) return;

            KeyModifiers mods = 0;
            if (e.Control) mods |= KeyModifiers.Control;
            if (e.Alt) mods |= KeyModifiers.Alt;
            if (e.Shift) mods |= KeyModifiers.Shift;

            if (mods != 0)
            {
                SelectedKey = e.KeyCode;
                SelectedModifiers = mods;
                _lblInfo.Text = $"Selected:\n{mods} + {e.KeyCode}";
            }
        }
    }
}
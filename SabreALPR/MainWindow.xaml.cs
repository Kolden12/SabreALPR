using System;
using System.IO;
using System.Linq;
using System.Timers;
using System.Windows;
using LibVLCSharp.Shared;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private MediaPlayer? _mediaPlayer;
        private System.Timers.Timer? _cleanupTimer;
        
        // Settings for Sabre Security Patrol Unit
        private readonly string _localCapturePath = @"C:\SabreALPR\Captures";
        private readonly string _remoteServerPath = @"\\10.0.0.5\SabreBackups"; // Change to your Home Lab VPN IP

        public MainWindow()
        {
            InitializeComponent();
            
            // Ensure the capture directory exists so the app doesn't crash
            if (!Directory.Exists(_localCapturePath))
            {
                Directory.CreateDirectory(_localCapturePath);
            }

            // Initialize VLC for the VSR-20 RTSP Stream
            Core.Initialize();
            _libVLC = new LibVLC();
            _mediaPlayer = new MediaPlayer(_libVLC);
            LiveVideoFeed.MediaPlayer = _mediaPlayer;

            // Connect to the Color stream on the first camera (.100)
            var media = new Media(_libVLC, new Uri("rtsp://pi:12345@192.168.3.100:8080/camcolor"), ":network-caching=300");
            _mediaPlayer.Play(media);

            // Setup the 'Janitor' Timer (Runs every 1 hour)
            _cleanupTimer = new System.Timers.Timer(3600000); 
            _cleanupTimer.Elapsed += OnCleanupTimerElapsed;
            _cleanupTimer.AutoReset = true;
            _cleanupTimer.Enabled = true;
        }

        private void OnCleanupTimerElapsed(object? sender, ElapsedEventArgs e)
        {
            ProcessCleanup();
        }

        private void ProcessCleanup()
        {
            try 
            {
                // 1. THE JANITOR: Delete unverified noise
                var directory = new DirectoryInfo(_localCapturePath);
                
                // Look at files older than 10 minutes to allow current reads to finish
                var oldFiles = directory.GetFiles().Where(f => f.LastWriteTime < DateTime.Now.AddMinutes(-10));

                foreach (var file in oldFiles)
                {
                    // If the YOLO 'hit' didn't result in a 'verified' plate read, delete it.
                    if (!file.Name.Contains("verified", StringComparison.OrdinalIgnoreCase))
                    {
                        file.Delete();
                    }
                }

                // 2. OFFLOAD: Move verified reads to Home Lab via Unifi VPN
                if (Directory.Exists(_remoteServerPath))
                {
                    var verifiedFiles = Directory.GetFiles(_localCapturePath, "*verified*");
                    foreach (var file in verifiedFiles)
                    {
                        string destPath = Path.Combine(_remoteServerPath, file.Name);
                        File.Move(file.FullName, destPath, true);
                    }
                }
            }
            catch (Exception ex)
            {
                // Log errors to a local file for troubleshooting later
                File.AppendAllText(Path.Combine(_localCapturePath, "sabre_log.txt"), $"{DateTime.Now}: {ex.Message}\n");
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            _cleanupTimer?.Dispose();
            base.OnClosed(e);
        }
    }
}
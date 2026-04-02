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
        
        private readonly string _localCapturePath = @"C:\SabreALPR\Captures";
        private readonly string _remoteServerPath = @"\\10.0.0.5\SabreBackups"; 

        public MainWindow()
        {
            InitializeComponent();
            
            if (!Directory.Exists(_localCapturePath))
            {
                Directory.CreateDirectory(_localCapturePath);
            }

            Core.Initialize();
            _libVLC = new LibVLC();
            _mediaPlayer = new MediaPlayer(_libVLC);
            
            // This now works because LiveVideoFeed is a VideoView, not an Image
            LiveVideoFeed.MediaPlayer = _mediaPlayer;

            var media = new Media(_libVLC, new Uri("rtsp://pi:12345@192.168.3.100:8080/camcolor"), ":network-caching=300");
            _mediaPlayer.Play(media);

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
                var directory = new DirectoryInfo(_localCapturePath);
                
                // Get files older than 10 mins
                var oldFiles = directory.GetFiles().Where(f => f.LastWriteTime < DateTime.Now.AddMinutes(-10));

                foreach (var file in oldFiles)
                {
                    if (!file.Name.Contains("verified", StringComparison.OrdinalIgnoreCase))
                    {
                        file.Delete();
                    }
                }

                // Offload verified files to VPN server
                if (Directory.Exists(_remoteServerPath))
                {
                    // Use GetFiles() to return FileInfo objects
                    var verifiedFiles = directory.GetFiles("*verified*");
                    foreach (var file in verifiedFiles)
                    {
                        string destPath = Path.Combine(_remoteServerPath, file.Name);
                        // File.Move uses FullName (the path) and Name (the file name)
                        File.Move(file.FullName, destPath, true);
                    }
                }
            }
            catch (Exception ex)
            {
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
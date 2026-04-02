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
        private LibVLC _libVLC;
        private MediaPlayer _mediaPlayer;
        private Timer _cleanupTimer;
        private string _localCapturePath = @"C:\SabreALPR\Captures";
        private string _remoteServerPath = @"\\10.0.0.5\SabreBackups"; // Replace with your VPN Home Lab IP

        public MainWindow()
        {
            InitializeComponent();
            Core.Initialize();

            _libVLC = new LibVLC();
            _mediaPlayer = new MediaPlayer(_libVLC);
            LiveVideoFeed.MediaPlayer = _mediaPlayer;

            // Start the Color Stream from the first camera
            var media = new Media(_libVLC, new Uri("rtsp://pi:12345@192.168.3.100:8080/camcolor"), ":network-caching=300");
            _mediaPlayer.Play(media);

            // Initialize the Hourly Cleanup and Offload Timer
            _cleanupTimer = new Timer(3600000); // 1 Hour in milliseconds
            _cleanupTimer.Elapsed += OnCleanupTimerElapsed;
            _cleanupTimer.AutoReset = true;
            _cleanupTimer.Enabled = true;
        }

        private void OnCleanupTimerElapsed(object sender, ElapsedEventArgs e)
        {
            ProcessCleanup();
        }

        private void ProcessCleanup()
        {
            try 
            {
                // 1. DELETE UNVERIFIED IMAGES
                // Logic: Find all files in local capture path not marked as 'Confirmed'
                var files = Directory.GetFiles(_localCapturePath);
                foreach (var file in files)
                {
                    // If the filename doesn't contain "CONFIRMED" (or your specific ALPR software tag), delete it
                    if (!file.Contains("CONFIRMED"))
                    {
                        File.Delete(file);
                    }
                }

                // 2. OFFLOAD TO HOME LAB VIA VPN
                if (Directory.Exists(_remoteServerPath))
                {
                    var confirmedFiles = Directory.GetFiles(_localCapturePath, "*CONFIRMED*");
                    foreach (var file in confirmedFiles)
                    {
                        string destFile = Path.Combine(_remoteServerPath, Path.GetFileName(file));
                        File.Move(file, destFile); // Move transfers the file and clears local space
                    }
                }
            }
            catch (Exception ex)
            {
                // Log error to a local text file for troubleshooting in the field
                File.AppendAllText("error_log.txt", $"{DateTime.Now}: {ex.Message}\n");
            }
        }
    }
}
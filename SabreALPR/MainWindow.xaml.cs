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

// Inside your ProcessCleanup() method in MainWindow.xaml.cs

        private void ProcessCleanup()
        {
            try 
            {
                // 1. DELETE UNVERIFIED IMAGES
                // Based on your script, verified reads start with "hit_"
                var files = Directory.GetFiles(_localCapturePath);
                foreach (var file in files)
                {
                    string fileName = Path.GetFileName(file);
                    // If it doesn't start with 'hit_', it's a "miss" or junk—toss it.
                    if (!fileName.StartsWith("hit_", StringComparison.OrdinalIgnoreCase))
                    {
                        File.Delete(file);
                    }
                }

                // 2. HOURLY OFFLOAD (VPN to Home Lab)
                // Check if the Unifi VPN is active (can we see the server?)
                if (Directory.Exists(_remoteServerPath))
                {
                    var verifiedFiles = Directory.GetFiles(_localCapturePath, "hit_*");
                    foreach (var file in verifiedFiles)
                    {
                        string destFile = Path.Combine(_remoteServerPath, Path.GetFileName(file));
                        // Move clears local car storage and sends to your home lab
                        File.Move(file, destFile, true); 
                    }
                }
            }
            catch (Exception ex)
            {
                // Log locally so you can check it when the car is back at the shop
                File.AppendAllText("sabre_debug.txt", $"{DateTime.Now}: {ex.Message}\n");
            }
        }
    }
}
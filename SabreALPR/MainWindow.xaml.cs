using System;
using System.Collections.Generic;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using LibVLCSharp.Shared;
using Newtonsoft.Json;
using Microsoft.VisualBasic;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;
        private readonly string _configPath = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), "SabreALPR", "cameras.json");
        
        public List<CameraConfig> CameraList { get; set; } = new List<CameraConfig>();

        public MainWindow()
        {
            InitializeComponent();
            EnsureConfigDirectory();
            LoadCameras();
            InitializeVLC();
            RefreshCameraMenu();
        }

        private void EnsureConfigDirectory()
        {
            string? dir = Path.GetDirectoryName(_configPath);
            if (dir != null && !Directory.Exists(dir)) Directory.CreateDirectory(dir);
        }

        private void LoadCameras()
        {
            if (File.Exists(_configPath))
            {
                try {
                    var json = File.ReadAllText(_configPath);
                    CameraList = JsonConvert.DeserializeObject<List<CameraConfig>>(json) ?? new List<CameraConfig>();
                } catch { CameraList = new List<CameraConfig>(); }
            }
            
            if (CameraList.Count == 0)
            {
                // Default setup for your bench-test Avenger board
                CameraList.Add(new CameraConfig { Name = "Front Center", IP = "192.168.3.102" });
            }
        }

        private void RefreshCameraMenu()
        {
            if (ViewMenu == null) return;
            ViewMenu.Items.Clear();
            foreach (var cam in CameraList)
            {
                var item = new MenuItem { Header = cam.Name, Tag = cam.IP };
                item.Click += (s, e) => SwitchCamera(cam.IP);
                ViewMenu.Items.Add(item);
            }
        }

        private void SwitchCamera(string ip)
        {
            if (_libVLC == null || _mediaPlayer == null) return;

            // Target the HTTP MJPEG stream found on port 8080
            string cameraUrl = $"http://{ip}:8080/camcolor";
            
            // Optimized options for high-def Avenger streams across the .1 to .3 VLANs
            var mediaOptions = new[] 
            { 
                ":network-caching=1000", 
                ":demux=mjpeg",
                ":http-reconnect",
                ":no-audio",
                ":http-continuous",
                ":clock-synchro=0" // Disables sync to save CPU on the gaming rig/mobile PC
            };

            try 
            {
                // Stop previous stream if running to clear memory
                if (_mediaPlayer.IsPlaying) _mediaPlayer.Stop();
                
                using var media = new Media(_libVLC, new Uri(cameraUrl), mediaOptions);
                _mediaPlayer.Play(media);
            }
            catch (Exception ex)
            {
                MessageBox.Show($"SabreALPR Connection Error: {ex.Message}");
            }
        }

        private void AddCamera_Click(object sender, RoutedEventArgs e)
        {
            string name = Interaction.InputBox("Enter Camera Name (e.g. Front Right):", "Add Camera", "New Camera");
            string ip = Interaction.InputBox("Enter Camera IP Address:", "Add Camera IP", "192.168.3.xxx");

            if (!string.IsNullOrWhiteSpace(name) && !string.IsNullOrWhiteSpace(ip))
            {
                CameraList.Add(new CameraConfig { Name = name, IP = ip });
                File.WriteAllText(_configPath, JsonConvert.SerializeObject(CameraList));
                RefreshCameraMenu();
            }
        }

        private void ClearCameras_Click(object sender, RoutedEventArgs e)
        {
            if (MessageBox.Show("Delete all saved cameras?", "Confirm", MessageBoxButton.YesNo) == MessageBoxResult.Yes)
            {
                CameraList.Clear();
                if (File.Exists(_configPath)) File.Delete(_configPath);
                RefreshCameraMenu();
            }
        }

        private void InitializeVLC()
        {
            try {
                Core.Initialize();
                
                // Hardware acceleration hints for your Gaming PC's GPU
                _libVLC = new LibVLC("--no-osd", "--no-video-title-show", "--ffmpeg-hw", "--clock-jitter=0");
                _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
                
                if (LiveVideoFeed != null) 
                {
                    LiveVideoFeed.MediaPlayer = _mediaPlayer;
                }

                // Auto-start the first camera in the list
                if (CameraList.Count > 0) SwitchCamera(CameraList[0].IP);
            } catch (Exception ex) {
                MessageBox.Show($"VLC Engine Init Failure: {ex.Message}");
            }
        }

        private void Stealth_Click(object sender, RoutedEventArgs e)
        {
            if (StealthMenu == null || BannerPanel == null || PlateText == null) return;
            bool isNight = StealthMenu.IsChecked;
            
            // Sabre Security standard: Dark Red for night operations
            BannerPanel.Background = isNight ? Brushes.Black : new SolidColorBrush(Color.FromRgb(44, 62, 80));
            PlateText.Foreground = isNight ? Brushes.DarkRed : new SolidColorBrush(Color.FromRgb(241, 196, 15));
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Application.Current.Shutdown();

        protected override void OnClosed(EventArgs e)
        {
            // Explicit cleanup to prevent background VLC processes from hanging
            _mediaPlayer?.Stop();
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            base.OnClosed(e);
        }
    }

    public class CameraConfig
    {
        public string Name { get; set; } = "";
        public string IP { get; set; } = "";
    }
}
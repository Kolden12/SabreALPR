using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using LibVLCSharp.Shared;
using Newtonsoft.Json;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;
        private readonly string _configPath = @"C:\SabreALPR\cameras.json";
        public List<CameraDevice> Cameras { get; set; } = new List<CameraDevice>();

        public MainWindow()
        {
            InitializeComponent();
            LoadCameraConfig();
            InitializeVLC();
            BuildCameraMenu();
        }

        private void LoadCameraConfig()
        {
            if (File.Exists(_configPath))
            {
                try {
                    string json = File.ReadAllText(_configPath);
                    Cameras = JsonConvert.DeserializeObject<List<CameraDevice>>(json) ?? new List<CameraDevice>();
                } catch { Cameras = GetDefaultCameras(); }
            }
            else { Cameras = GetDefaultCameras(); SaveCameraConfig(); }
        }

        private List<CameraDevice> GetDefaultCameras() => new List<CameraDevice> {
            new CameraDevice { Name = "Front Center", IP = "192.168.3.102" },
            new CameraDevice { Name = "Front Right", IP = "192.168.3.101" }
        };

        private void SaveCameraConfig() => File.WriteAllText(_configPath, JsonConvert.SerializeObject(Cameras));

        private void BuildCameraMenu()
        {
            ViewMenu.Items.Clear();
            foreach (var cam in Cameras)
            {
                var item = new MenuItem { Header = cam.Name, Tag = cam.IP };
                item.Click += (s, e) => SwitchToCamera(cam.IP);
                ViewMenu.Items.Add(item);
            }
        }

        private void SwitchToCamera(string ip)
        {
            if (_libVLC == null || _mediaPlayer == null) return;
            var uri = new Uri($"rtsp://{ip}:8080/camcolor");
            using var media = new Media(_libVLC, uri, ":network-caching=300");
            _mediaPlayer.Play(media);
        }

        private void ManageCameras_Click(object sender, RoutedEventArgs e)
        {
            // Simple prompt logic for demo - in a full app, this would open a sub-window
            string input = Microsoft.VisualBasic.Interaction.InputBox("Enter Name and IP (Name,IP):", "Add Camera", "Rear,192.168.3.104");
            if (!string.IsNullOrEmpty(input) && input.Contains(","))
            {
                var parts = input.Split(',');
                Cameras.Add(new CameraDevice { Name = parts[0], IP = parts[1] });
                SaveCameraConfig();
                BuildCameraMenu();
                MessageBox.Show("Camera Added to Fleet.");
            }
        }

        private void InitializeVLC()
        {
            Core.Initialize();
            _libVLC = new LibVLC();
            _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
            if (LiveVideoFeed != null) LiveVideoFeed.MediaPlayer = _mediaPlayer;
            
            // Start with first camera if available
            if (Cameras.Count > 0) SwitchToCamera(Cameras[0].IP);
        }

        private void ToggleStealth_Click(object sender, RoutedEventArgs e)
        {
            bool isStealth = ((MenuItem)sender).IsChecked;
            BannerPanel.Background = isStealth ? Brushes.Black : new SolidColorBrush(Color.FromRgb(44, 62, 80));
            PlateText.Foreground = isStealth ? Brushes.DarkRed : new SolidColorBrush(Color.FromRgb(241, 196, 15));
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Application.Current.Shutdown();

        protected override void OnClosed(EventArgs e)
        {
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            base.OnClosed(e);
        }
    }

    public class CameraDevice
    {
        public string Name { get; set; } = "";
        public string IP { get; set; } = "";
    }
}
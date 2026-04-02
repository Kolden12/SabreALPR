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
                CameraList.Add(new CameraConfig { Name = "Front Center", IP = "192.168.3.102" });
            }
        }

        private void RefreshCameraMenu()
        {
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
            using var media = new Media(_libVLC, new Uri($"rtsp://{ip}:8080/camcolor"), ":network-caching=300");
            _mediaPlayer.Play(media);
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
                _libVLC = new LibVLC();
                _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
                if (LiveVideoFeed != null) LiveVideoFeed.MediaPlayer = _mediaPlayer;
                if (CameraList.Count > 0) SwitchCamera(CameraList[0].IP);
            } catch (Exception ex) {
                MessageBox.Show($"VLC Init Error: {ex.Message}");
            }
        }

        private void Stealth_Click(object sender, RoutedEventArgs e)
        {
            bool isNight = StealthMenu.IsChecked;
            BannerPanel.Background = isNight ? Brushes.Black : new SolidColorBrush(Color.FromRgb(44, 62, 80));
            PlateText.Foreground = isNight ? Brushes.DarkRed : new SolidColorBrush(Color.FromRgb(241, 196, 15));
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Application.Current.Shutdown();

        protected override void OnClosed(EventArgs e)
        {
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
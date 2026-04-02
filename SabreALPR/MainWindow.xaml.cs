using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Net.Http;
using System.Text;
using System.Windows;
using System.Windows.Media;
using LibVLCSharp.Shared;
using Newtonsoft.Json;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;
        private readonly string _cadEndpoint = "http://10.0.0.5:5000/api/alerts"; // Your Home Lab CAD IP

        public MainWindow()
        {
            InitializeComponent();
            InitializeVLC();
            ApplyTacticalDefaults();
        }

        private void ApplyTacticalDefaults()
        {
            // Auto-Stealth Logic: If between 8 PM and 6 AM, go Red-on-Black
            int currentHour = DateTime.Now.Hour;
            if (currentHour >= 20 || currentHour <= 6)
            {
                SetStealthMode(true);
            }
        }

        private void InitializeVLC()
        {
            try 
            {
                Core.Initialize();
                _libVLC = new LibVLC();
                _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
                
                if (LiveVideoFeed != null)
                {
                    LiveVideoFeed.MediaPlayer = _mediaPlayer;
                }

                if (_libVLC != null)
                {
                    // Defaulting to Front-Center Camera (.102)
                    var media = new Media(_libVLC, new Uri("rtsp://192.168.3.102:8080/camcolor"), ":network-caching=300");
                    _mediaPlayer.Play(media);
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show($"VLC Engine Failure: {ex.Message}. Ensure 64-bit VLC is installed.");
            }
        }

        private async void SendCadHeartbeat(string plate, string state)
        {
            try 
            {
                using var client = new HttpClient();
                var payload = new {
                    Unit = "Interceptor-1",
                    Plate = plate,
                    State = state,
                    Timestamp = DateTime.Now,
                    Lat = "29.4241", // Manual San Antonio Lat until GPS hardware is linked
                    Lon = "-98.4936"
                };

                var content = new StringContent(JsonConvert.SerializeObject(payload), Encoding.UTF8, "application/json");
                await client.PostAsync(_cadEndpoint, content);
            }
            catch { /* Patrol continues even if VPN is spotty */ }
        }

        private void SetStealthMode(bool enabled)
        {
            if (BannerPanel != null)
            {
                BannerPanel.Background = enabled ? Brushes.Black : new SolidColorBrush(Color.FromRgb(44, 62, 80));
                PlateText.Foreground = enabled ? Brushes.DarkRed : new SolidColorBrush(Color.FromRgb(241, 196, 15));
            }
        }

        private void SwitchCam_Click(object sender, RoutedEventArgs e)
        {
            if (_libVLC == null || _mediaPlayer == null) return;
            if (sender is System.Windows.Controls.MenuItem item && item.Tag != null)
            {
                var uri = new Uri($"rtsp://192.168.3.{item.Tag}:8080/camcolor");
                using var media = new Media(_libVLC, uri, ":network-caching=300");
                _mediaPlayer.Play(media);
            }
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Application.Current.Shutdown();

        protected override void OnClosed(EventArgs e)
        {
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            base.OnClosed(e);
        }
    }
}
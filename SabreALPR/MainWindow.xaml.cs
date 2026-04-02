using System;
using System.Windows;
using LibVLCSharp.Shared;

namespace SabreALPR
{
    // The 'partial' keyword is mandatory to link to the XAML
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;

        public MainWindow()
        {
            // This call should stop showing an error once the .csproj and .xaml are saved
            InitializeComponent();
            InitializeVLC();
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

                if (_libVLC != null && _mediaPlayer != null)
                {
                    var media = new Media(_libVLC, new Uri("rtsp://192.168.3.102:8080/camcolor"), ":network-caching=300");
                    _mediaPlayer.Play(media);
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine($"VLC Error: {ex.Message}");
            }
        }

        private void SwitchCam_Click(object sender, RoutedEventArgs e)
        {
            if (_libVLC == null || _mediaPlayer == null) return;
            if (sender is System.Windows.Controls.MenuItem item && item.Tag != null)
            {
                using var media = new Media(_libVLC, new Uri($"rtsp://192.168.3.{item.Tag}:8080/camcolor"), ":network-caching=300");
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
using System;
using System.Windows;
using LibVLCSharp.Shared;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;

        public MainWindow()
        {
            // This method is created in a hidden file during build. 
            // It will only be found if the .csproj link is successful.
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
                
                // If the compiler still doesn't see this, the XAML parsing failed.
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
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
            // This call is generated automatically if the XAML is linked correctly
            this.InitializeComponent();
            InitializeVLC();
        }

        private void InitializeVLC()
        {
            Core.Initialize();
            _libVLC = new LibVLC();
            _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
            
            // Using 'this.' to force the compiler to look at the XAML-defined name
            if (this.LiveVideoFeed != null)
            {
                this.LiveVideoFeed.MediaPlayer = _mediaPlayer;
            }

            if (_libVLC != null)
            {
                var media = new Media(_libVLC, new Uri("rtsp://192.168.3.102:8080/camcolor"), ":network-caching=300");
                _mediaPlayer.Play(media);
            }
        }

        private void SwitchCam_Click(object sender, RoutedEventArgs e)
        {
            if (_libVLC == null || _mediaPlayer == null) return;
            if (sender is System.Windows.Controls.MenuItem item && item.Tag != null)
            {
                var media = new Media(_libVLC, new Uri($"rtsp://192.168.3.{item.Tag}:8080/camcolor"), ":network-caching=300");
                _mediaPlayer.Play(media);
            }
        }

        private void Exit_Click(object sender, RoutedEventArgs e) => Application.Current.Shutdown();
    }
}
using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Media;
using System.Timers;
using System.Windows;
using System.Windows.Media.Imaging;
using LibVLCSharp.Shared;
using Newtonsoft.Json;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        private MediaPlayer? _mediaPlayer;
        private System.Timers.Timer? _cleanupTimer;
        private FileSystemWatcher? _watcher;
        
        // Sound Players
        private SoundPlayer? _readSound;
        private SoundPlayer? _hotlistSound;

        public ObservableCollection<PlateRead> ReadHistory { get; set; } = new ObservableCollection<PlateRead>();

        private readonly string _localCapturePath = @"C:\SabreALPR\Captures";
        private readonly string _soundPath = @"C:\SabreALPR\Sounds";
        private readonly string _remoteServerPath = @"\\10.0.0.5\SabreBackups"; 

        public MainWindow()
        {
            InitializeComponent();
            DataContext = this;
            HistoryGrid.ItemsSource = ReadHistory;
            
            // Ensure directories exist
            if (!Directory.Exists(_localCapturePath)) Directory.CreateDirectory(_localCapturePath);
            if (!Directory.Exists(_soundPath)) Directory.CreateDirectory(_soundPath);

            // Initialize Sounds
            try {
                _readSound = new SoundPlayer(Path.Combine(_soundPath, "read.wav"));
                _hotlistSound = new SoundPlayer(Path.Combine(_soundPath, "hotlist.wav"));
            } catch { /* Sounds missing - fail silently */ }

            // Initialize VLC
            Core.Initialize();
            _libVLC = new LibVLC();
            _mediaPlayer = new MediaPlayer(_libVLC);
            LiveVideoFeed.MediaPlayer = _mediaPlayer;

            var media = new Media(_libVLC, new Uri("rtsp://pi:12345@192.168.3.100:8080/camcolor"), ":network-caching=300");
            _mediaPlayer.Play(media);

            SetupFileWatcher();

            _cleanupTimer = new System.Timers.Timer(3600000); 
            _cleanupTimer.Elapsed += (s, e) => ProcessCleanup();
            _cleanupTimer.AutoReset = true;
            _cleanupTimer.Enabled = true;
        }

        private void SetupFileWatcher()
        {
            _watcher = new FileSystemWatcher(_localCapturePath, "*.json");
            _watcher.Created += OnNewReadDetected;
            _watcher.EnableRaisingEvents = true;
        }

        private void OnNewReadDetected(object sender, FileSystemEventArgs e)
        {
            System.Threading.Thread.Sleep(250); // Delay to ensure file write is finished

            try {
                string jsonContent = File.ReadAllText(e.FullPath);
                var read = JsonConvert.DeserializeObject<PlateRead>(jsonContent);

                if (read != null) {
                    Application.Current.Dispatcher.Invoke(() => {
                        // Update UI
                        PlateText.Text = $"PLATE: {read.Plate}";
                        StateText.Text = $"STATE: {read.State}";
                        VehicleColor.Text = $"COLOR: {read.Color}";
                        VehicleMake.Text = $"MAKE: {read.Make}";
                        VehicleModel.Text = $"MODEL: {read.Model}";

                        string imgPath = e.FullPath.Replace(".json", ".jpg");
                        if (File.Exists(imgPath)) {
                            ConfirmedPlateImage.Source = new BitmapImage(new Uri(imgPath));
                        }

                        // Play the appropriate sound
                        if (read.IsHotlist) {
                            _hotlistSound?.Play();
                            PlateText.Foreground = System.Windows.Media.Brushes.Red; // Visual Alert for Hotlist
                        } else {
                            _readSound?.Play();
                            PlateText.Foreground = System.Windows.Media.Brushes.White;
                        }

                        ReadHistory.Insert(0, read);
                        if (ReadHistory.Count > 15) ReadHistory.RemoveAt(15);
                    });
                }
            } catch { }
        }

        private void ProcessCleanup()
        {
            try {
                var directory = new DirectoryInfo(_localCapturePath);
                var oldFiles = directory.GetFiles().Where(f => f.LastWriteTime < DateTime.Now.AddMinutes(-10));

                foreach (var file in oldFiles) {
                    if (!file.Name.Contains("verified", StringComparison.OrdinalIgnoreCase)) {
                        file.Delete();
                    }
                }

                if (Directory.Exists(_remoteServerPath)) {
                    foreach (var file in directory.GetFiles("*verified*")) {
                        File.Move(file.FullName, Path.Combine(_remoteServerPath, file.Name), true);
                    }
                }
            } catch (Exception ex) {
                File.AppendAllText(Path.Combine(_localCapturePath, "sabre_log.txt"), $"{DateTime.Now}: {ex.Message}\n");
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            _watcher?.Dispose();
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            _cleanupTimer?.Dispose();
            _readSound?.Dispose();
            _hotlistSound?.Dispose();
            base.OnClosed(e);
        }
    }

    public class PlateRead
    {
        public string Plate { get; set; } = "--";
        public string State { get; set; } = "--";
        public string Color { get; set; } = "--";
        public string Make { get; set; } = "--";
        public string Model { get; set; } = "--";
        public bool IsHotlist { get; set; } = false; // NEW: Trigger for the alarm sound
        public string Timestamp { get; set; } = DateTime.Now.ToString("HH:mm:ss");
    }
}
using System;
using System.Collections.ObjectModel;
using System.IO;
using System.Linq;
using System.Media;
using System.Timers;
using System.Windows;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using LibVLCSharp.Shared;
using Newtonsoft.Json;

namespace SabreALPR
{
    public partial class MainWindow : Window
    {
        private LibVLC? _libVLC;
        
        // FIX: Explicitly tell the compiler to use LibVLCSharp's MediaPlayer
        private LibVLCSharp.Shared.MediaPlayer? _mediaPlayer;
        
        private System.Timers.Timer? _cleanupTimer;
        private FileSystemWatcher? _watcher;
        
        private SoundPlayer? _readSound;
        private SoundPlayer? _hotlistSound;

        public ObservableCollection<PlateRead> ReadHistory { get; set; } = new ObservableCollection<PlateRead>();

        private readonly string _localCapturePath = @"C:\SabreALPR\Captures";
        private readonly string _networkCapturePath = @"Z:\"; 
        private readonly string _soundPath = @"C:\SabreALPR\Sounds";
        private readonly string _remoteServerPath = @"\\10.0.0.5\SabreBackups"; 

        public MainWindow()
        {
            InitializeComponent();
            DataContext = this;
            HistoryGrid.ItemsSource = ReadHistory;
            
            InitializeEnvironment();
            InitializeVLC();
            SetupFileWatcher();

            _cleanupTimer = new System.Timers.Timer(60000); 
            _cleanupTimer.Elapsed += (s, e) => ProcessCleanup();
            _cleanupTimer.AutoReset = true;
            _cleanupTimer.Enabled = true;
        }

        private void InitializeEnvironment()
        {
            if (!Directory.Exists(_localCapturePath)) Directory.CreateDirectory(_localCapturePath);
            if (!Directory.Exists(_soundPath)) Directory.CreateDirectory(_soundPath);

            try {
                _readSound = new SoundPlayer(Path.Combine(_soundPath, "read.wav"));
                _hotlistSound = new SoundPlayer(Path.Combine(_soundPath, "hotlist.wav"));
            } catch { }
        }

        private void InitializeVLC()
        {
            Core.Initialize();
            _libVLC = new LibVLC();
            
            // FIX: Explicitly initialize the correct MediaPlayer type
            _mediaPlayer = new LibVLCSharp.Shared.MediaPlayer(_libVLC);
            
            LiveVideoFeed.MediaPlayer = _mediaPlayer;

            // Targeting Camera 3 Color as default based on your Python setup
            var media = new Media(_libVLC, new Uri("rtsp://pi:12345@192.168.3.102:8080/camcolor"), ":network-caching=300");
            
            // This will now work because _mediaPlayer is confirmed as a LibVLCSharp object
            _mediaPlayer.Play(media);
        }

        private void SetupFileWatcher()
        {
            string watchPath = Directory.Exists(_networkCapturePath) ? _networkCapturePath : _localCapturePath;
            
            _watcher = new FileSystemWatcher(watchPath, "*.json");
            _watcher.Created += OnNewReadDetected;
            _watcher.EnableRaisingEvents = true;
        }

        private void OnNewReadDetected(object sender, FileSystemEventArgs e)
        {
            System.Threading.Thread.Sleep(250); 

            try {
                string jsonContent = File.ReadAllText(e.FullPath);
                var read = JsonConvert.DeserializeObject<PlateRead>(jsonContent);

                if (read != null) {
                    Application.Current.Dispatcher.Invoke(() => {
                        UpdateDashboard(read, e.FullPath);
                    });
                }
            } catch { }
        }

        private void UpdateDashboard(PlateRead read, string jsonPath)
        {
            PlateText.Text = $"PLATE: {read.Plate}";
            StateText.Text = $"STATE: {read.State}";
            VehicleColor.Text = $"COLOR: {read.Color}";
            VehicleMake.Text = $"MAKE: {read.Make}";
            VehicleModel.Text = $"MODEL: {read.Model}";

            string imgPath = jsonPath.Replace(".json", ".jpg");
            if (File.Exists(imgPath)) {
                ConfirmedPlateImage.Source = new BitmapImage(new Uri(imgPath));
            }

            if (read.IsHotlist) {
                _hotlistSound?.Play();
                PlateText.Foreground = System.Windows.Media.Brushes.Red;
            } else {
                _readSound?.Play();
                // Impact Yellow styling from your original Python app
                PlateText.Foreground = new SolidColorBrush(System.Windows.Media.Color.FromRgb(241, 196, 15)); 
            }

            ReadHistory.Insert(0, read);
            if (ReadHistory.Count > 10) ReadHistory.RemoveAt(10);
        }

        private void ProcessCleanup()
        {
            try {
                CleanupFolder(_localCapturePath);
                if (Directory.Exists(_networkCapturePath)) CleanupFolder(_networkCapturePath);

                if (Directory.Exists(_remoteServerPath)) {
                    var dir = new DirectoryInfo(_localCapturePath);
                    foreach (var file in dir.GetFiles("*verified*")) {
                        File.Move(file.FullName, Path.Combine(_remoteServerPath, file.Name), true);
                    }
                }
            } catch { }
        }

        private void CleanupFolder(string path)
        {
            var directory = new DirectoryInfo(path);
            var oldFiles = directory.GetFiles().Where(f => f.LastWriteTime < DateTime.Now.AddMinutes(-10));

            foreach (var file in oldFiles) {
                if (!file.Name.Contains("verified", StringComparison.OrdinalIgnoreCase)) {
                    file.Delete();
                }
            }
        }

        protected override void OnClosed(EventArgs e)
        {
            _watcher?.Dispose();
            _mediaPlayer?.Dispose();
            _libVLC?.Dispose();
            _cleanupTimer?.Dispose();
            base.OnClosed(e);
        }
    }

    public class PlateRead
    {
        public string Timestamp { get; set; } = DateTime.Now.ToString("yyyy-MM-dd HH:mm");
        public string Plate { get; set; } = "----";
        public string State { get; set; } = "--";
        public string Color { get; set; } = "----";
        public string Make { get; set; } = "----";
        public string Model { get; set; } = "----";
        public string CameraSource { get; set; } = "CAM-01";
        public bool IsHotlist { get; set; } = false;
    }
}
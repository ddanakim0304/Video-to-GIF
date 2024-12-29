import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QMessageBox,
    QSpinBox, QHBoxLayout
)
from moviepy.video.io.VideoFileClip import VideoFileClip

class VideoToGifConverter(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Video to GIF Converter")
        self.setGeometry(300, 300, 400, 250)

        layout = QVBoxLayout()

        # File size limit input
        size_layout = QHBoxLayout()
        size_label = QLabel("Max file size (MB):")
        self.size_input = QSpinBox()
        self.size_input.setRange(1, 100)  # Allow sizes between 1MB and 100MB
        self.size_input.setValue(5)  # Default to 5MB
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_input)
        size_layout.addStretch()
        layout.addLayout(size_layout)

        self.label = QLabel("Select a video file to convert to GIF.")
        layout.addWidget(self.label)

        self.select_button = QPushButton("Select Video")
        self.select_button.clicked.connect(self.select_video)
        layout.addWidget(self.select_button)

        self.convert_button = QPushButton("Convert to GIF")
        self.convert_button.clicked.connect(self.convert_to_gif)
        self.convert_button.setEnabled(False)
        layout.addWidget(self.convert_button)

        self.setLayout(layout)

        self.video_path = None

    def select_video(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Video File", "", 
            "Video Files (*.mp4 *.avi *.mov *.mkv)", 
            options=options
        )

        if file_path:
            self.video_path = file_path
            self.label.setText(f"Selected Video: {os.path.basename(file_path)}")
            self.convert_button.setEnabled(True)

    def convert_with_ffmpeg(self, input_path, output_path, scale_factor=1.0, fps=5):
        """Convert video to GIF using FFmpeg with specified scaling and FPS."""
        try:
            # Calculate new width (height will scale automatically)
            probe = subprocess.run([
                'ffprobe', 
                '-v', 'error',
                '-select_streams', 'v:0',
                '-show_entries', 'stream=width',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                input_path
            ], capture_output=True, text=True)
            
            original_width = int(probe.stdout.strip())
            new_width = int(original_width * scale_factor)
            
            # Ensure width is even number (required by some codecs)
            new_width = new_width - (new_width % 2)
            
            # Convert to palette-based GIF for better quality
            palette_path = output_path + "_palette.png"
            
            # Generate palette
            subprocess.run([
                'ffmpeg', '-i', input_path,
                '-vf', f'fps={fps},scale={new_width}:-1:flags=lanczos,palettegen',
                '-y', palette_path
            ])
            
            # Convert to GIF using the palette
            subprocess.run([
                'ffmpeg', '-i', input_path, '-i', palette_path,
                '-lavfi', f'fps={fps},scale={new_width}:-1:flags=lanczos [x]; [x][1:v] paletteuse',
                '-y', output_path
            ])
            
            # Clean up palette file
            os.remove(palette_path)
            
            return True
        except Exception as e:
            print(f"FFmpeg conversion error: {e}")
            return False

    def convert_to_gif(self):
        if not self.video_path:
            QMessageBox.warning(self, "Error", "Please select a video file first.")
            return

        max_file_size = self.size_input.value() * 1024 * 1024  # Convert MB to bytes
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save GIF As", "output.gif", "GIF Files (*.gif)"
        )

        if save_path:
            try:
                # Get original video info
                clip = VideoFileClip(self.video_path)
                initial_fps = max(10, int(clip.fps / 2))  # Start with reduced FPS
                clip.close()
                
                # First attempt at conversion
                scale_factor = 1.0
                success = self.convert_with_ffmpeg(self.video_path, save_path, scale_factor, initial_fps)
                
                if not success:
                    raise Exception("FFmpeg conversion failed")
                
                # If file is too large, try reducing quality until it fits
                attempts = 0
                while os.path.getsize(save_path) > max_file_size and attempts < 5:
                    os.remove(save_path)  # Remove the oversized file
                    attempts += 1
                    
                    # Reduce quality with each attempt
                    scale_factor *= 0.7  # Reduce size by 30%
                    fps = max(5, int(initial_fps * (0.8 ** attempts)))  # Reduce FPS by 20% each time
                    
                    success = self.convert_with_ffmpeg(self.video_path, save_path, scale_factor, fps)
                    if not success:
                        raise Exception("FFmpeg conversion failed during resize attempt")
                
                # Final size check
                if os.path.getsize(save_path) > max_file_size:
                    os.remove(save_path)
                    QMessageBox.warning(
                        self, 
                        "Error", 
                        f"Could not reduce GIF to under {self.size_input.value()} MB. "
                        "Try reducing the video length or choosing a larger file size limit."
                    )
                else:
                    final_size_mb = os.path.getsize(save_path) / (1024 * 1024)
                    QMessageBox.information(
                        self, 
                        "Success", 
                        f"GIF saved to: {save_path}\nFinal size: {final_size_mb:.2f} MB"
                    )
            
            except Exception as e:
                QMessageBox.critical(
                    self, 
                    "Error", 
                    f"Failed to convert video to GIF:\n{e}"
                )
            finally:
                self.label.setText("Select a video file to convert to GIF.")
                self.convert_button.setEnabled(False)
                self.video_path = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    converter = VideoToGifConverter()
    converter.show()
    sys.exit(app.exec_())
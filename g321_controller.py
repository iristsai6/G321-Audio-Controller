import sys
import json
import os
import time
import threading
from datetime import datetime

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QSlider, QPushButton, QComboBox, QMessageBox, QCheckBox, QInputDialog
)
from PyQt6.QtCore import Qt, QCoreApplication, pyqtSignal, QObject, QTimer
from PyQt6.QtGui import QIcon
import pystray
from PIL import Image

from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
from comtypes import CLSCTX_ALL

# 自動抓取目前 .exe 所在的資料夾路徑
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_FILE = os.path.join(BASE_DIR, "g321_config.json")
APO_CONFIG_PATH = r"C:\Program Files\EqualizerAPO\config\config.txt"
ICON_FILE = os.path.join(BASE_DIR, "g321icon.ico")

DEFAULT_CONFIG = {
    "自定義模式": {"volume": 60, "mic_volume": 70, "eq": [15, 10, 0, 0, 15, 15]},
    "遊戲模式": {"volume": 60, "mic_volume": 80, "eq": [30, 10, -15, 0, 40, 20]},
    "音樂模式": {"volume": 60, "mic_volume": 60, "eq": [35, 20, 0, 0, 15, 25]},
    "追劇模式": {"volume": 60, "mic_volume": 60, "eq": [30, 15, -10, 5, 25, 20]},
    "語音會議": {"volume": 60, "mic_volume": 80, "eq": [-20, -15, 0, 10, 35, -10]}
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved_data = json.load(f)
                if isinstance(saved_data, dict):
                    for k, v in saved_data.items():
                        config[k] = v
        except Exception:
            pass
    return config

def save_config(config_data):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [錯誤] 無法儲存設定檔: {e}")


class SignalBus(QObject):
    open_gui_signal = pyqtSignal()
    apply_profile_signal = pyqtSignal(str)
    update_tray_menu_signal = pyqtSignal()
    battery_update_signal = pyqtSignal(int, str)


class EQControlPanel(QWidget):
    """G321 音效控制面板"""
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.config_data = load_config()
        
        self.setWindowTitle("G321 音效控制面板")
        self.resize(480, 650)  
        
        if os.path.exists(ICON_FILE):
            self.setWindowIcon(QIcon(ICON_FILE))
            
        self.init_ui()
        self.load_profile_to_ui("遊戲模式")
        self.refresh_device_list()
        
        # 綁定電量更新訊號
        self.controller.signal_bus.battery_update_signal.connect(self.update_battery_ui)

    def init_ui(self):
        self.setStyleSheet("""
            QWidget {
                background-color: #121212;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 13px;
            }
            QLabel {
                color: #b3b3b3;
            }
            QComboBox {
                background-color: #282828;
                color: #ffffff;
                border: 1px solid #333333;
                border-radius: 4px;
                padding: 5px 10px;
            }
            QComboBox::drop-down {
                border: 0px;
            }
            QComboBox QAbstractItemView {
                background-color: #282828;
                color: #ffffff;
                selection-background-color: #1db954;
            }
            QPushButton {
                background-color: #1db954;
                color: #ffffff;
                border: none;
                border-radius: 16px;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #1ed760;
            }
            QPushButton#sub_btn {
                background-color: #282828;
                color: #b3b3b3;
                border-radius: 14px;
                padding: 5px 10px;
            }
            QPushButton#sub_btn:hover {
                background-color: #3e3e3e;
                color: #ffffff;
            }
            QPushButton#del_btn {
                background-color: #282828;
                color: #ff5555;
                border-radius: 14px;
                padding: 5px 10px;
            }
            QPushButton#del_btn:hover {
                background-color: #3e3e3e;
                color: #ff7777;
            }
            QPushButton#spotify_btn {
                background-color: #303332;
                color: #ffffff;
                border-radius: 14px;
                padding: 5px 12px;
            }
            QPushButton#spotify_btn:hover {
                background-color: #78cf97;
            }
            QPushButton#reset_btn {
                background-color: #282828;
                color: #b3b3b3;
            }
            QPushButton#reset_btn:hover {
                background-color: #3e3e3e;
                color: #ffffff;
            }
            QCheckBox {
                color: #b3b3b3;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background-color: #282828;
                border: 1px solid #535353;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background-color: #1db954;
                border: 1px solid #1db954;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #535353;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #1db954;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                width: 12px;
                height: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::groove:vertical {
                width: 4px;
                background: #535353;
                border-radius: 2px;
            }
            QSlider::add-page:vertical {
                background: #1db954;
                border-radius: 2px;
            }
            QSlider::sub-page:vertical {
                background: #535353;
                border-radius: 2px;
            }
            QSlider::handle:vertical {
                background: #ffffff;
                height: 12px;
                width: 12px;
                margin: 0 -4px;
                border-radius: 6px;
            }
        """)

        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(20, 15, 20, 15)
        main_layout.setSpacing(12)

        # 0. 頂部狀態列 (模擬電量與 Spotify 快捷按鈕)
        status_layout = QHBoxLayout()
        self.battery_lbl = QLabel("🔋 模擬電量: 90% (白燈恆亮)")
        self.battery_lbl.setStyleSheet("color: #1db954; font-weight: bold;")
        
        spotify_btn = QPushButton("開啟 Spotify")
        spotify_btn.setObjectName("spotify_btn")
        spotify_btn.clicked.connect(self.open_spotify)

        status_layout.addWidget(self.battery_lbl)
        status_layout.addStretch()
        status_layout.addWidget(spotify_btn)
        main_layout.addLayout(status_layout)

        # 手動燈號狀態設定 (校準模擬電量)
        battery_set_layout = QHBoxLayout()
        batt_set_lbl = QLabel("耳機燈號校準：")
        batt_set_lbl.setFixedWidth(95)
        self.batt_combo = QComboBox()
        self.batt_combo.addItems([
            "🟢 滿電 / 白燈恆亮 (約 90%)", 
            "🟡 中等 / 白燈閃爍 (約 50%)", 
            "🔴 低電量 / 紅燈閃爍 (約 20%)"
        ])
        self.batt_combo.currentIndexChanged.connect(self.on_battery_status_changed)
        battery_set_layout.addWidget(batt_set_lbl)
        battery_set_layout.addWidget(self.batt_combo, stretch=1)
        main_layout.addLayout(battery_set_layout)

        # 音訊輸出裝置選擇與「重新搜尋」按鈕
        device_layout = QHBoxLayout()
        device_lbl = QLabel("播放裝置：")
        device_lbl.setFixedWidth(95)
        self.device_combo = QComboBox()
        self.device_combo.currentIndexChanged.connect(self.on_device_changed)
        
        refresh_btn = QPushButton("🔄 重新搜尋")
        refresh_btn.setObjectName("sub_btn")
        refresh_btn.clicked.connect(self.refresh_device_list)

        device_layout.addWidget(device_lbl)
        device_layout.addWidget(self.device_combo, stretch=1)
        device_layout.addWidget(refresh_btn)
        main_layout.addLayout(device_layout)

        # 1. 預設模式選擇與【新增模式】、【刪除模式】按鈕
        top_layout = QHBoxLayout()
        profile_lbl = QLabel("預設音樂集：")
        profile_lbl.setFixedWidth(95)
        self.profile_combo = QComboBox()
        self.update_profile_dropdown()
        self.profile_combo.currentTextChanged.connect(self.load_profile_to_ui)
        
        add_profile_btn = QPushButton("➕ 新增")
        add_profile_btn.setObjectName("sub_btn")
        add_profile_btn.clicked.connect(self.on_add_profile_clicked)

        del_profile_btn = QPushButton("🗑️ 刪除")
        del_profile_btn.setObjectName("del_btn")
        del_profile_btn.clicked.connect(self.on_delete_profile_clicked)

        top_layout.addWidget(profile_lbl)
        top_layout.addWidget(self.profile_combo, stretch=1)
        top_layout.addWidget(add_profile_btn)
        top_layout.addWidget(del_profile_btn)
        main_layout.addLayout(top_layout)

        # 2. 耳機輸出音量
        vol_layout = QHBoxLayout()
        vol_lbl = QLabel("耳機主音量")
        vol_lbl.setFixedWidth(95)
        self.vol_slider = QSlider(Qt.Orientation.Horizontal)
        self.vol_slider.setRange(0, 100)
        self.vol_val_lbl = QLabel("80%")
        self.vol_val_lbl.setFixedWidth(40)
        self.vol_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.vol_slider.valueChanged.connect(self.on_volume_slider_changed)
        
        vol_layout.addWidget(vol_lbl)
        vol_layout.addWidget(self.vol_slider)
        vol_layout.addWidget(self.vol_val_lbl)
        main_layout.addLayout(vol_layout)

        # 3. 麥克風音量與靜音
        mic_layout = QHBoxLayout()
        mic_lbl = QLabel("麥克風音量")
        mic_lbl.setFixedWidth(95)
        self.mic_slider = QSlider(Qt.Orientation.Horizontal)
        self.mic_slider.setRange(0, 100)
        self.mic_val_lbl = QLabel("70%")
        self.mic_val_lbl.setFixedWidth(40)
        self.mic_val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.mic_slider.valueChanged.connect(self.on_mic_slider_changed)
        
        self.mic_mute_chk = QCheckBox("麥克風靜音")
        self.mic_mute_chk.stateChanged.connect(self.on_mic_mute_changed)

        mic_layout.addWidget(mic_lbl)
        mic_layout.addWidget(self.mic_slider)
        mic_layout.addWidget(self.mic_val_lbl)
        mic_layout.addWidget(self.mic_mute_chk)
        main_layout.addLayout(mic_layout)

        line = QLabel()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #282828;")
        main_layout.addWidget(line)

        eq_title = QLabel("等化器微調 (Equalizer - 0.1dB)")
        eq_title.setStyleSheet("font-weight: bold; color: #ffffff; font-size: 13px;")
        main_layout.addWidget(eq_title)

        sliders_layout = QHBoxLayout()
        sliders_layout.setSpacing(15)

        self.bands = [
            ("60Hz", 60),
            ("150Hz", 150),
            ("400Hz", 400),
            ("1KHz", 1000),
            ("2.4KHz", 2400),
            ("15KHz", 15000)
        ]
        
        self.sliders = {}
        self.val_labels = {}

        for name, freq in self.bands:
            col_layout = QVBoxLayout()
            col_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            col_layout.setSpacing(6)
            
            val_lbl = QLabel("+0.0dB")
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            val_lbl.setStyleSheet("color: #1db954; font-weight: bold; font-size: 10px;")
            
            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-120, 120)
            slider.setValue(0)
            slider.setFixedHeight(85)
            
            freq_lbl = QLabel(name)
            freq_lbl.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            freq_lbl.setStyleSheet("font-size: 11px; color: #b3b3b3;")
            
            slider.valueChanged.connect(lambda v, l=val_lbl: l.setText(f"{v/10.0:+.1f}dB"))
            slider.valueChanged.connect(self.on_eq_slider_changed)
            
            self.sliders[freq] = slider
            self.val_labels[freq] = val_lbl
            
            col_layout.addWidget(val_lbl)
            col_layout.addWidget(slider, alignment=Qt.AlignmentFlag.AlignHCenter)
            col_layout.addWidget(freq_lbl)
            
            sliders_layout.addLayout(col_layout)

        main_layout.addLayout(sliders_layout)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        save_btn = QPushButton("💾 儲存設定")
        save_btn.clicked.connect(self.save_eq_settings)
        
        reset_btn = QPushButton("重設")
        reset_btn.setObjectName("reset_btn")
        reset_btn.clicked.connect(self.reset_to_default)
        
        btn_layout.addStretch()
        btn_layout.addWidget(reset_btn)
        btn_layout.addWidget(save_btn)
        main_layout.addLayout(btn_layout)

        self.setLayout(main_layout)

    def update_battery_ui(self, pct, status_text):
        if pct > 20:
            self.battery_lbl.setText(f"🔋 模擬電量: {pct}% ({status_text})")
            self.battery_lbl.setStyleSheet("color: #1db954; font-weight: bold;")
        else:
            self.battery_lbl.setText(f"⚠️ 模擬電量低: {pct}% ({status_text} - 請充電)")
            self.battery_lbl.setStyleSheet("color: #ff5555; font-weight: bold;")

    def open_spotify(self):
        try:
            os.startfile("spotify:")
        except Exception:
            try:
                spotify_path = os.path.expanduser(r"~\AppData\Roaming\Spotify\Spotify.exe")
                if os.path.exists(spotify_path):
                    os.startfile(spotify_path)
                else:
                    QMessageBox.warning(self, "提示", "找不到 Spotify 應用程式，請確認是否已安裝。")
            except Exception as e:
                QMessageBox.warning(self, "錯誤", f"無法開啟 Spotify: {e}")

    def update_profile_dropdown(self):
        self.config_data = load_config()
        self.profile_combo.blockSignals(True)
        current_text = self.profile_combo.currentText()
        self.profile_combo.clear()
        for name in self.config_data.keys():
            self.profile_combo.addItem(name)
        
        idx = self.profile_combo.findText(current_text)
        if idx >= 0:
            self.profile_combo.setCurrentIndex(idx)
        elif self.profile_combo.count() > 0:
            self.profile_combo.setCurrentIndex(0)
        self.profile_combo.blockSignals(False)

    def on_add_profile_clicked(self):
        text, ok = QInputDialog.getText(self, "新增模式", "請輸入新音效模式名稱：")
        if ok and text.strip():
            new_name = text.strip()
            self.config_data = load_config()
            if new_name in self.config_data:
                QMessageBox.warning(self, "提示", f"模式「{new_name}」已存在！")
                return
            
            vol = self.vol_slider.value()
            mic_vol = self.mic_slider.value()
            eq_vals = [self.sliders[freq].value() for _, freq in self.bands]
            
            self.config_data[new_name] = {
                "volume": vol,
                "mic_volume": mic_vol,
                "eq": eq_vals
            }
            save_config(self.config_data)
            self.update_profile_dropdown()
            
            self.controller.signal_bus.update_tray_menu_signal.emit()
            
            idx = self.profile_combo.findText(new_name)
            if idx >= 0:
                self.profile_combo.setCurrentIndex(idx)
            QMessageBox.information(self, "成功", f"已成功新增並儲存模式「{new_name}」！")

    def on_delete_profile_clicked(self):
        current_profile = self.profile_combo.currentText()
        protected_defaults = ["自定義模式", "遊戲模式", "音樂模式", "追劇模式", "語音會議"]
        
        if current_profile in protected_defaults:
            QMessageBox.warning(self, "提示", f"【{current_profile}】屬於系統預設核心模式，無法刪除！")
            return
            
        reply = QMessageBox.question(
            self, "確認刪除", f"確定要刪除自定義模式「{current_profile}」嗎？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.config_data = load_config()
            if current_profile in self.config_data:
                del self.config_data[current_profile]
                save_config(self.config_data)
                self.update_profile_dropdown()
                self.controller.signal_bus.update_tray_menu_signal.emit()
                QMessageBox.information(self, "成功", f"已成功刪除模式「{current_profile}」！")

    def refresh_device_list(self):
        devices = []
        try:
            speakers = AudioUtilities.GetSpeakers()
            if speakers:
                try:
                    devices.append(speakers.FriendlyName)
                except Exception:
                    devices.append("預設耳機 / 揚聲器")
        except Exception:
            pass

        if not devices:
            devices.append("預設音訊裝置")

        self.device_combo.blockSignals(True)
        current_text = self.device_combo.currentText()
        self.device_combo.clear()
        for dev in devices:
            self.device_combo.addItem(dev)
        
        idx = self.device_combo.findText(current_text)
        if idx >= 0:
            self.device_combo.setCurrentIndex(idx)
        else:
            self.device_combo.setCurrentIndex(0)
        self.device_combo.blockSignals(False)

        pct = int(self.controller.sim_battery_pct)
        status = self.controller.sim_status_text
        self.update_battery_ui(pct, status)

    def on_device_changed(self, index):
        dev_name = self.device_combo.currentText()
        if dev_name:
            self.controller.set_active_playback_device(dev_name)

    def on_battery_status_changed(self, index):
        base_pcts = [90, 50, 20]
        status_texts = ["白燈恆亮", "白燈閃爍", "紅燈閃爍"]
        if index < len(base_pcts):
            self.controller.set_simulated_battery_level(base_pcts[index], status_texts[index])
            pct = int(base_pcts[index])
            self.update_battery_ui(pct, status_texts[index])

    def on_volume_slider_changed(self, value):
        self.vol_val_lbl.setText(f"{value}%")
        self.controller.set_system_volume(value)

    def on_mic_slider_changed(self, value):
        self.mic_val_lbl.setText(f"{value}%")
        self.controller.set_microphone_volume(value)

    def on_mic_mute_changed(self, state):
        is_muted = (state == Qt.CheckState.Checked.value)
        self.controller.set_microphone_mute(is_muted)

    def on_eq_slider_changed(self):
        current_profile = self.profile_combo.currentText()
        self.config_data = load_config()
        if not current_profile or current_profile not in self.config_data:
            return
        vol = self.vol_slider.value()
        mic_vol = self.mic_slider.value()
        eq_vals = [self.sliders[freq].value() for _, freq in self.bands]
        
        self.config_data[current_profile] = {
            "volume": vol,
            "mic_volume": mic_vol,
            "eq": eq_vals
        }
        save_config(self.config_data)
        self.controller.apply_eq_settings(eq_vals)

    def load_profile_to_ui(self, profile_name):
        self.config_data = load_config()
        if not profile_name or profile_name not in self.config_data:
            return
        data = self.config_data[profile_name]
        
        vol = data.get("volume", 70)
        self.vol_slider.blockSignals(True)
        self.vol_slider.setValue(vol)
        self.vol_val_lbl.setText(f"{vol}%")
        self.vol_slider.blockSignals(False)
        
        mic_vol = data.get("mic_volume", 70)
        self.mic_slider.blockSignals(True)
        self.mic_slider.setValue(mic_vol)
        self.mic_val_lbl.setText(f"{mic_vol}%")
        self.mic_slider.blockSignals(False)
        
        eq_values = data.get("eq", [0, 0, 0, 0, 0, 0])
        
        for _, slider in self.sliders.items():
            slider.blockSignals(True)
            
        for i, (_, freq) in enumerate(self.bands):
            if i < len(eq_values):
                val = eq_values[i]
                self.sliders[freq].setValue(val)
                if freq in self.val_labels:
                    self.val_labels[freq].setText(f"{val/10.0:+.1f}dB")
                
        for _, slider in self.sliders.items():
            slider.blockSignals(False)
            
        self.controller.apply_profile_settings(profile_name, vol, mic_vol, eq_values)

    def save_eq_settings(self):
        current_profile = self.profile_combo.currentText()
        self.config_data = load_config()
        if current_profile:
            vol = self.vol_slider.value()
            mic_vol = self.mic_slider.value()
            eq_vals = [self.sliders[freq].value() for _, freq in self.bands]
            
            self.config_data[current_profile] = {
                "volume": vol,
                "mic_volume": mic_vol,
                "eq": eq_vals
            }
            save_config(self.config_data)
            self.controller.apply_eq_settings(eq_vals)
            self.controller.signal_bus.update_tray_menu_signal.emit()
            QMessageBox.information(self, "成功", f"【{current_profile}】設定已同步並儲存成功！")

    def reset_to_default(self):
        self.config_data = DEFAULT_CONFIG.copy()
        save_config(self.config_data)
        self.update_profile_dropdown()
        self.load_profile_to_ui(self.profile_combo.currentText())
        self.controller.signal_bus.update_tray_menu_signal.emit()
        QMessageBox.information(self, "重設", "已恢復原廠預設設定！")


class G321ControllerApp:
    def __init__(self):
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        self.signal_bus = SignalBus()
        self.signal_bus.open_gui_signal.connect(self.show_eq_window)
        self.signal_bus.apply_profile_signal.connect(self.quick_apply_profile)
        self.signal_bus.update_tray_menu_signal.connect(self.update_tray_menu)
        
        self.eq_window = None
        self.icon = None
        self.selected_device_name = None
        
        # 模擬電量初始狀態
        self.sim_battery_pct = 90.0
        self.sim_status_text = "白燈恆亮"
        
        # 啟動背景掉電監控執行緒
        threading.Thread(target=self.battery_drain_worker, daemon=True).start()

    def set_simulated_battery_level(self, pct, status_txt):
        self.sim_battery_pct = float(pct)
        self.sim_status_text = status_txt

    def battery_drain_worker(self):
        """背景自動掉電執行緒：每隔一段時間扣 1%，最低到 5%"""
        while True:
            time.sleep(60)  # 每 20 秒模擬掉電 1% (可自行調整秒數)
            if self.sim_battery_pct > 5.0:
                self.sim_battery_pct -= 1.0
                
                # 根據剩餘電量自動切換燈號描述
                if self.sim_battery_pct > 60:
                    self.sim_status_text = "白燈恆亮"
                elif self.sim_battery_pct > 20:
                    self.sim_status_text = "白燈閃爍"
                else:
                    self.sim_status_text = "紅燈閃爍"
                    
                current_pct = int(self.sim_battery_pct)
                self.signal_bus.battery_update_signal.emit(current_pct, self.sim_status_text)

    def set_active_playback_device(self, dev_name):
        self.selected_device_name = dev_name

    def set_system_volume(self, level_percent):
        try:
            devices = AudioUtilities.GetSpeakers()
            volume = devices.EndpointVolume
            scalar = max(0.0, min(1.0, level_percent / 100.0))
            if volume.GetMute():
                volume.SetMute(0, None)
            volume.SetMasterVolumeLevelScalar(scalar, None)
        except Exception as e:
            print(f"[錯誤] 音量調整失敗: {e}")

    def set_microphone_volume(self, level_percent):
        try:
            device = AudioUtilities.GetMicrophone()
            if device:
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                scalar = max(0.0, min(1.0, level_percent / 100.0))
                volume.SetMasterVolumeLevelScalar(scalar, None)
        except Exception as e:
            print(f"[錯誤] 麥克風音量調整失敗: {e}")

    def set_microphone_mute(self, is_muted):
        try:
            device = AudioUtilities.GetMicrophone()
            if device:
                interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                volume = interface.QueryInterface(IAudioEndpointVolume)
                volume.SetMute(1 if is_muted else 0, None)
        except Exception as e:
            print(f"[錯誤] 麥克風靜音切換失敗: {e}")

    def apply_eq_settings(self, eq_values):
        db_values = [v / 10.0 for v in eq_values]
        frequencies = [60, 150, 400, 1000, 2400, 15000]
        try:
            with open(APO_CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write("# Auto-generated by G321 Master Controller\n")
                f.write("Preamp: 0 dB\n")
                for freq, gain in zip(frequencies, db_values):
                    f.write(f"Filter: ON PK Fc {freq} Hz Gain {gain:.1f} dB Q 1.0\n")
        except Exception as e:
            print(f"[提示] 無法寫入 Equalizer APO 設定檔: {e}")

    def apply_profile_settings(self, profile_name, volume, mic_volume, eq_values):
        self.set_system_volume(volume)
        self.set_microphone_volume(mic_volume)
        self.apply_eq_settings(eq_values)

    def quick_apply_profile(self, profile_name):
        config = load_config()
        if profile_name in config:
            data = config[profile_name]
            self.apply_profile_settings(profile_name, data.get("volume", 70), data.get("mic_volume", 70), data.get("eq", [0]*6))
            if self.eq_window:
                self.eq_window.update_profile_dropdown()
                self.eq_window.profile_combo.blockSignals(True)
                index = self.eq_window.profile_combo.findText(profile_name)
                if index >= 0:
                    self.eq_window.profile_combo.setCurrentIndex(index)
                self.eq_window.load_profile_to_ui(profile_name)
                self.eq_window.profile_combo.blockSignals(False)

    def show_eq_window(self):
        try:
            if not self.eq_window:
                self.eq_window = EQControlPanel(self)
            self.eq_window.show()
            self.eq_window.raise_()
            self.eq_window.activateWindow()
        except Exception as e:
            print(f"[錯誤] 開啟面板失敗: {e}")

    def create_tray_image(self):
        if os.path.exists(ICON_FILE):
            return Image.open(ICON_FILE)
        else:
            image = Image.new('RGB', (64, 64), color=(18, 18, 18))
            return image

    def build_tray_menu(self):
        def make_action(profile_name):
            def action(icon, item):
                self.signal_bus.apply_profile_signal.emit(profile_name)
            return action

        config = load_config()
        menu_items = [
            pystray.MenuItem('🎧 G321 音效控制器', lambda icon, item: None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('🎛️ 開啟控制與混音面板', lambda icon, item: self.signal_bus.open_gui_signal.emit()),
            pystray.Menu.SEPARATOR,
        ]

        for name in config.keys():
            menu_items.append(
                pystray.MenuItem(f'🎵 {name}', make_action(name))
            )

        menu_items.extend([
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('結束程式', self.quit_app)
        ])

        return pystray.Menu(*menu_items)

    def update_tray_menu(self):
        if self.icon:
            self.icon.menu = self.build_tray_menu()

    def run_pystray(self):
        self.icon = pystray.Icon("G321_Controller", self.create_tray_image(), "[G321 Controller]", menu=self.build_tray_menu())
        self.icon.run()

    def quit_app(self, icon, item):
        icon.stop()
        QCoreApplication.quit()

    def start(self):
        threading.Thread(target=self.run_pystray, daemon=True).start()
        sys.exit(self.app.exec())

if __name__ == '__main__':
    controller = G321ControllerApp()
    controller.start()

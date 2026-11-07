#!/usr/bin/env python3

# LSL Live Differential Spectral Analysis & qEEG Indices
#
# Dependencies:
#  pip install pylsl scipy numpy

import sys
import argparse
import threading
from collections import deque
import tkinter as tk
from tkinter import messagebox
import numpy as np
from pylsl import StreamInlet, resolve_byprop
from scipy.signal import welch, iirnotch, lfilter

VERSION_MAJOR = 1
VERSION_MINOR = 0

class LSLLiveCanvasApp:

    def __init__(
        self,
        root,
        prop,
        value,
        channel_idx_1,
        channel_idx_2,
        notch_freq,
        alarm_duration_sec,
        alarm_threshold_pct) -> None:

        self.root = root
        self.root.title("LSL Live Differential Spectral Analysis & qEEG Indices")
        self.root.geometry("1100x580")
        self.root.configure(bg="#f4f4f6")

        self.prop = prop
        self.value = value
        self.channel_idx_1 = int(channel_idx_1)
        self.channel_idx_2 = int(channel_idx_2)
        self.notch_freq = float(notch_freq)
        
        # ALARM: 3Hz Absence Seizure
        self.alarm_duration_sec = float(alarm_duration_sec)  # Duration requirement in seconds
        self.alarm_threshold_pct = float(alarm_threshold_pct)  # Amplitude spike threshold percentage
        
        self.inlet = None
        self.sfreq = 100.0  # Sampling frequency (will update dynamically from stream info)
        self.is_running = False

        self.seizure_frames_counter = 0
        self.update_interval_ms = 100  # Refresh loop duration (10 Hz rendering rate)

        self.buffer_size = 300
        self.buffer_ch1 = deque(maxlen=self.buffer_size)
        self.buffer_ch2 = deque(maxlen=self.buffer_size)

        self.target_freqs = np.arange(1, 41, 1)

        top_frame = tk.Frame(root, bg="#f4f4f6", pady=10)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        self.lbl_status = tk.Label(top_frame, text=f"Searching for LSL stream ({prop}='{value}')...", 
                                   font=("Arial", 11, "bold"), bg="#f4f4f6", fg="#d97706")
        self.lbl_status.pack(side=tk.LEFT, padx=20)

        main_container = tk.Frame(root, bg="#f4f4f6")
        main_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.canvas_width = 750
        self.canvas_height = 430
        self.canvas = tk.Canvas(main_container, width=self.canvas_width, height=self.canvas_height, bg="white", bd=0, highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.panel_indices = tk.LabelFrame(main_container, text=" Clinical Indices ", font=("Arial", 10, "bold"), bg="white", padx=15, pady=15, width=220)
        self.panel_indices.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))
        self.panel_indices.pack_propagate(False)

        self.lbl_dar = tk.Label(self.panel_indices, text="DAR (Delta/Alpha):\n--", font=("Arial", 11), bg="white", justify=tk.LEFT)
        self.lbl_dar.pack(anchor="w", pady=10)

        self.lbl_tbr = tk.Label(self.panel_indices, text="TBR (Theta/Beta):\n--", font=("Arial", 11), bg="white", justify=tk.LEFT)
        self.lbl_tbr.pack(anchor="w", pady=10)

        settings_text = f"Alarm Config:\nThreshold: >{self.alarm_threshold_pct}%\nTime Lock: {self.alarm_duration_sec}s"
        self.lbl_alarm_settings = tk.Label(self.panel_indices, text=settings_text, font=("Arial", 9, "italic"), bg="white", fg="#4b5563", justify=tk.LEFT)
        self.lbl_alarm_settings.pack(anchor="w", pady=10)

        self.alert_frame = tk.Frame(self.panel_indices, bg="#ef4444", padx=10, pady=10)
        self.lbl_alert = tk.Label(self.alert_frame, text="3Hz EPI ALARM\nNORMAL", font=("Arial", 11, "bold"), bg="#ef4444", fg="white")
        self.lbl_alert.pack()
        self.alert_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=10)
        self.set_alarm_state(False) 

        self.canvas.bind("<Configure>", self.on_canvas_resize)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.notch_b = None
        self.notch_a = None

        self.start_lsl_thread()

    def set_alarm_state(
        self,
        is_active) -> None:

        if is_active:
            self.alert_frame.config(bg="#dc2626")
            self.lbl_alert.config(bg="#dc2626", text="3Hz EPI ALARM\nSEIZURE DETECTED!")
        else:
            self.alert_frame.config(bg="#16a34a")
            self.lbl_alert.config(bg="#16a34a", text="3Hz EPI ALARM\nNORMAL STATE")

    def on_canvas_resize(
        self,
        event) -> None:

        self.canvas_width = event.width
        self.canvas_height = event.height
        self.draw_static_axes()

    def start_lsl_thread(self) -> None:

        self.is_running = True
        self.lsl_thread = threading.Thread(target=self.lsl_worker, daemon=True)
        self.lsl_thread.start()

    def lsl_worker(self) -> None:

        try:
            streams = resolve_byprop(self.prop, self.value, timeout=5.0)
            if not streams:
                self.root.after(0, lambda: self.lbl_status.config(
                    text=f"Error: Stream with {self.prop}='{self.value}' not found.", fg="#dc2626"))
                return

            self.inlet = StreamInlet(streams[0])
            stream_info = self.inlet.info()
            self.sfreq = stream_info.nominal_srate()
            total_channels = stream_info.channel_count()

            if self.channel_idx_1 >= total_channels or self.channel_idx_2 >= total_channels:
                self.root.after(0, lambda: messagebox.showerror(
                    "Channel Error", f"Stream contains only {total_channels} channels. Indices [{self.channel_idx_1}, {self.channel_idx_2}] are out of range."))
                self.is_running = False
                return

            Q = 30.0
            if self.sfreq > (self.notch_freq * 2):
                self.notch_b, self.notch_a = iirnotch(self.notch_freq, Q, fs=self.sfreq)
                filter_status = f"Active {self.notch_freq}Hz Notch Filter"
            else:
                filter_status = "Notch Filter Inactive"

            self.buffer_size = int(self.sfreq * 3)
            self.buffer_ch1 = deque(maxlen=self.buffer_size)
            self.buffer_ch2 = deque(maxlen=self.buffer_size)

            stream_name = stream_info.name()
            diff_text = f"Differential ({self.channel_idx_1} - {self.channel_idx_2})"
            self.root.after(0, lambda: self.lbl_status.config(
                text=f"Connected: {stream_name} ({self.sfreq}Hz) | {diff_text} | {filter_status}", fg="#16a34a"))

            self.root.after(100, self.update_plot)

            while self.is_running:
                chunk, timestamps = self.inlet.pull_chunk(timeout=0.05, max_samples=100)
                if chunk:
                    for sample in chunk:
                        self.buffer_ch1.append(sample[self.channel_idx_1])
                        self.buffer_ch2.append(sample[self.channel_idx_2])
        except Exception as e:
            print(f"LSL Engine Networking Error: {e}")

    def draw_static_axes(
        self,
        target_psd=None) -> None:

        self.canvas.delete("all")

        padding_left, padding_bottom, padding_top, padding_right = 60, 40, 20, 20
        graph_width = self.canvas_width - padding_left - padding_right
        graph_height = self.canvas_height - padding_top - padding_bottom

        max_val = np.max(target_psd) if (target_psd is not None and np.max(target_psd) > 0) else 1.0
        grid_lines = 4
        for i in range(grid_lines + 1):
            y = padding_top + graph_height - (i * (graph_height / grid_lines))
            val = (i * (max_val / grid_lines))
            self.canvas.create_line(padding_left, y, self.canvas_width - padding_right, y, fill="#e5e7eb", width=1)
            self.canvas.create_text(padding_left - 8, y, text=f"{val:.1e}", anchor="e", font=("Arial", 8), fill="#6b7280")

        num_bars = len(self.target_freqs)
        bar_gap = 2
        bar_width = (graph_width - (bar_gap * (num_bars - 1))) / num_bars

        for idx, freq in enumerate(self.target_freqs):
            x0 = padding_left + idx * (bar_width + bar_gap)
            x1 = x0 + bar_width

            if target_psd is not None:
                power_ratio = min(max(target_psd[idx] / max_val, 0.0), 1.0)
                y0 = padding_top + graph_height - (power_ratio * graph_height)
            else:
                y0 = padding_top + graph_height

            y1 = padding_top + graph_height

            if 8 <= freq <= 12:
                bar_color = "#f59e0b"  # Alpha Band (Orange)
            elif 12 < freq <= 30:
                bar_color = "#0284c7"  # Beta Band (Blue)
            elif freq == 3:
                bar_color = "#dc2626"  # Epilepsy Alert Focal Anchor (Crimson Red)
            else:
                bar_color = "#9ca3af"  # Other Sub-bands/Delta/Theta (Gray)
            self.canvas.create_rectangle(x0, y0, x1, y1, fill=bar_color, outline="")
            if freq % 2 != 0:
                self.canvas.create_text((x0 + x1) / 2, y1 + 12, text=str(freq), anchor="n", font=("Arial", 8), fill="#374151")
            self.canvas.create_line(padding_left, padding_top, padding_left, padding_top + graph_height, fill="#4b5563", width=2)
            self.canvas.create_line(padding_left, padding_top + graph_height, self.canvas_width - padding_right, padding_top + graph_height, fill="#4b5563", width=2)
            
    def calculate_indices(
        self,
        freqs, psd) -> None:

        delta_mask = (freqs >= 1) & (freqs < 4)
        theta_mask = (freqs >= 4) & (freqs < 8)
        alpha_mask = (freqs >= 8) & (freqs <= 12)
        beta_mask  = (freqs > 12) & (freqs <= 30)
        p_delta = np.mean(psd[delta_mask]) if np.any(delta_mask) else 0.001
        p_theta = np.mean(psd[theta_mask]) if np.any(theta_mask) else 0.001
        p_alpha = np.mean(psd[alpha_mask]) if np.any(alpha_mask) else 0.001
        p_beta  = np.mean(psd[beta_mask])  if np.any(beta_mask)  else 0.001
        dar = p_delta / p_alpha if p_alpha > 0 else 0
        tbr = p_theta / p_beta  if p_beta > 0  else 0
        mask_3hz = (freqs >= 2.5) & (freqs <= 3.5)
        p_3hz = np.max(psd[mask_3hz]) if np.any(mask_3hz) else 0
        baseline_mask = ~mask_3hz
        mean_baseline_power = np.mean(psd[baseline_mask]) if np.any(baseline_mask) else 1e-6
        required_multiplier = 1.0 + (self.alarm_threshold_pct / 100.0)
        threshold_crossed = (p_3hz > mean_baseline_power * required_multiplier) and (p_3hz > 1e-5)
        required_frames = int((self.alarm_duration_sec * 1000) / self.update_interval_ms)
        if threshold_crossed:
            self.seizure_frames_counter += 1
        else:
            self.seizure_frames_counter = 0  # Instantly reset array counter if drop-out artifact occurs
        is_alarm_active = self.seizure_frames_counter >= required_frames
        self.root.after(0, lambda: self.lbl_dar.config(text=f"DAR (Delta/Alpha):\n{dar:.2f}"))
        self.root.after(0, lambda: self.lbl_tbr.config(text=f"TBR (Theta/Beta):\n{tbr:.2f}"))
        self.root.after(0, lambda: self.set_alarm_state(is_alarm_active))

    def update_plot(self) -> None:

        if not self.is_running:
            return
        if len(self.buffer_ch1) > self.sfreq and len(self.buffer_ch2) > self.sfreq:
            len_to_use = min(len(self.buffer_ch1), len(self.buffer_ch2))
            ch1_data = np.array(self.buffer_ch1)[-len_to_use:]
            ch2_data = np.array(self.buffer_ch2)[-len_to_use:]
            signal_chunk = ch1_data - ch2_data
            if self.notch_b is not None and self.notch_a is not None:
                signal_chunk = lfilter(self.notch_b, self.notch_a, signal_chunk)
            signal_chunk = signal_chunk - np.mean(signal_chunk)
            nperseg = min(len(signal_chunk), 256)
            freqs, psd = welch(signal_chunk, fs=self.sfreq, nperseg=nperseg)
            try:
                target_psd = np.interp(self.target_freqs, freqs, psd)
                self.calculate_indices(freqs, psd)
                self.draw_static_axes(target_psd)
            except Exception as e:
                print(f"Data Processing Pipeline Exception Error: {e}")
        # rendering loop
        self.root.after(self.update_interval_ms, self.update_plot)

    def on_closing(self) -> None:
        self.is_running = False
        if self.inlet:
            del self.inlet
        self.root.destroy()
        sys.exit(0)

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"LSL Live Differential Spectral Analysis & qEEG Indices {VERSION_MAJOR}.{VERSION_MINOR}",
    )
    parser.add_argument("-p", "--prop", help='Channel property, default type', default="type")
    parser.add_argument("-v", "--value", default="EEG", help="Property value, default EEG")
    parser.add_argument("-f", "--first_idx", type=int, default=0, help="First channel index, default 0")
    parser.add_argument("-s", "--second_idx", type=int, default=1, help="Second channel index, default 1")
    parser.add_argument("-n", "--notch_freq", type=int, default=50, help="Frequency of a power supply, default 50")
    parser.add_argument("-t", "--threshold_pct", type=float, default=200.0, help="Alarm threshold percent for 3Hz Absence Seizure, default 200.0")
    parser.add_argument("-d", "--duration_sec", type=float, default=1.5, help="Alarm duration in seconds for 3Hz Absence Seizure, default 1.5")  
    return parser

if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    root = tk.Tk()
    app = LSLLiveCanvasApp(
        root,
        args.prop,
        args.value,
        args.first_idx,
        args.second_idx,
        args.notch_freq,
        args.duration_sec,
        args.threshold_pct
    )
    root.mainloop()

## LSL Live Differential Spectral Analysis

![AI Assisted](https://shields.io)

An experimental real-time Python application for streaming, filtering, and analyzing electroencephalography (EEG) data via the Lab Streaming Layer (LSL) protocol.

### Architecture

[ EEG Device / LSL ] -> ( UDP/TCP ) -> ( LAN ) -> [ Python EEG Spectral ]

Protocol: Lab Streaming Layer (LSL)

### Features

* Real-Time LSL Stream Integration: Automatically resolves and connects to active LSL EEG data streams.

* Differential Spectral Analysis: Computes Power Spectral Density (PSD) using Welch's method on differential channel pairs.

* Digital Filtering: Includes configurable IIR notch filtering to remove power line interference (e.g., 50Hz or 60Hz).

* Quantitative EEG (qEEG) Indices: Calculates standard clinical frequency band ratios:

    . DAR (Delta/Alpha Ratio)

    . TBR (Theta/Beta Ratio)

* Monitoring & Alert System: Detects specific rhythmic patterns (such as 3Hz activity) with adjustable amplitude thresholds and time duration locks.

* Graphical Interface: Built with tkinter, featuring live frequency band visualization and status readouts.

### Digital Signal Processing

To prevent data distortion and process chunks continuously, the system operates on a FIFO (First-In, First-Out) Sliding Window architecture.

    Temporal Window Size: 2.0 Seconds (equivalent to 512 samples at 256 Hz).
    Analysis Step Interval: ~100 ms (sliding window shifts and triggers evaluation 10 times per second).
    Preprocessing (Causal Filtering):
	- Cutoff Frequencies: 1.0 Hz to 30.0 Hz
	- Brum filtering
    Feature Extraction (Spectral Density):
	- Algorithm: Welch's Method (scipy.signal.welch) for Power Spectral Density (PSD) estimation.
    - Target Frequency Bin: Integration of absolute power in the 2.5 Hz ... 3.5 Hz band.
    Classification & Alarm Logic:
	- Mathematical thresholding evaluates the mean power within the target bin.
	- The system flags an immediate anomaly event (Potential Absence Seizure).

### Requirements

    $ pip install pylsl scipy numpy
    
### Command-Line Parameters

LSL Live Differential Spectral Analysis & qEEG Indices 1.0

    options:
    -h, --help            show this help message and exit
    -p PROP, --prop PROP  Channel property, defualt type
    -v VALUE, --value VALUE
                            Property value, default EEG
    -f FIRST_IDX, --first_idx FIRST_IDX
                            First channel index, default 0
    -s SECOND_IDX, --second_idx SECOND_IDX
                            Second channel index, default 1
    -n NOTCH_FREQ, --notch_freq NOTCH_FREQ
                            Frequency of a power supply, default 50
    -t THRESHOLD_PCT, --threshold_pct THRESHOLD_PCT
                            Alarm threshold percent for 3Hz Absence Seizure, default 200.0
    -d DURATION_SEC, --duration_sec DURATION_SEC
                            Alarm duration in seconds for 3Hz Absence Seizure, default 1.5

### Usage

To run the application with a 60Hz power line notch filter and custom channel indices: 2 and 3.

    $ python3 eeg_spectrum.py -n 60 -f 2 -s 3
    
To run the simulator:

    $ python3 eeg_simulator.py
    
### LSL Notes

* LSL streams are unencrypted by design

* LSL UDP multicast / broadcast ( Port 16571 ), TCP ( Ports 16571 to 16604 )

* LSL needs special network configuration for different LAN segments

* LSL can cause network overload

* Cheap LSL devices for EEG

    . OpenBCI - 8 channels (sampling rate at 250 Hz)

    . HackEEG ( by Starcat ) -  8 channels

    . Emotiv Insight -  5 channels rate 128Hz

    . OMNIFIT Brain / Mindcare - 2 channels

    . EMOTIV MN8 - 2 channels

    . BrainBit Headphones - 4 channels

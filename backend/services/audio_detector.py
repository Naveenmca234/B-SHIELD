"""
audio_detector.py
-----------------
Classical Digital Signal Processing (DSP) for border perimeter acoustic analysis.
Uses physical audio features:
- Root Mean Square (RMS) Energy (dBFS)
- Zero Crossing Rate (ZCR)
- Spectral Centroid (via FFT frequency distribution)

IMPORTANT OPERATIONAL POLICY:
Outputs are strictly labeled by observable physical characteristics:
- 'LOUD_IMPULSE_DETECTED' (sudden transient energy rise: breach impact, collision, detonation)
- 'SUSTAINED_LOUD_AUDIO' (continuous elevated acoustic noise: heavy engine, power tools)
- 'NORMAL_AMBIENT' (border environmental background noise)

Explicitly avoids speculative weapon/gunshot classification without dedicated
calibrated acoustic sensor arrays.
"""
import numpy as np
from typing import Dict, Any, Optional


class ClassicalAudioDetector:
    """
    Classical DSP acoustic analyzer for perimeter microphone sensors.
    Operates on 1D PCM audio arrays (float32 [-1.0, 1.0] or int16).
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        impulse_db_threshold: float = -28.0,
        sustained_db_threshold: float = -20.0,
        zcr_threshold: float = 0.10,
    ):
        self.sample_rate = sample_rate
        self.impulse_db_threshold = impulse_db_threshold
        self.sustained_db_threshold = sustained_db_threshold
        self.zcr_threshold = zcr_threshold

    def analyze_pcm(self, audio_samples: np.ndarray) -> Dict[str, Any]:
        """
        Analyzes a chunk of audio samples using classical DSP algorithms.
        """
        if audio_samples is None or len(audio_samples) < 64:
            return {
                "classification": "NORMAL_AMBIENT",
                "rms_db": -60.0,
                "zcr": 0.0,
                "spectral_centroid_hz": 0.0,
                "crest_factor": 1.0,
                "is_anomaly": False,
                "description": "Insufficient audio samples for analysis.",
            }

        # Normalize to float32 [-1.0, 1.0]
        samples = audio_samples.astype(np.float32)
        if np.max(np.abs(samples)) > 1.0:
            samples = samples / 32768.0

        # 1. Root Mean Square (RMS) Energy
        rms = np.sqrt(np.mean(samples ** 2) + 1e-12)
        rms_db = float(20 * np.log10(max(rms, 1e-6)))

        # 2. Zero Crossing Rate (ZCR)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(samples) >= 0)))
        zcr = float(zero_crossings / max(1, len(samples) - 1))

        # 3. Spectral Centroid via Real FFT
        fft_vals = np.abs(np.fft.rfft(samples))
        freq_bins = np.fft.rfftfreq(len(samples), 1.0 / self.sample_rate)
        sum_fft = np.sum(fft_vals)
        if sum_fft > 1e-9:
            spectral_centroid = float(np.sum(freq_bins * fft_vals) / sum_fft)
        else:
            spectral_centroid = 0.0

        # Peak to RMS ratio (Crest Factor) indicates impulsive transients
        peak = np.max(np.abs(samples))
        crest_factor = float(peak / (rms + 1e-6))

        # Classification based on deterministic acoustic metrics
        # Impulsive transient: sharp peak with high crest factor and elevated energy
        if (crest_factor >= 3.0 and rms_db >= self.impulse_db_threshold) or (peak >= 0.5 and rms_db >= self.impulse_db_threshold):
            classification = "LOUD_IMPULSE_DETECTED"
            is_anomaly = True
            description = (
                f"A sudden acoustic impulse was detected ({rms_db:.1f} dBFS, "
                f"crest factor {crest_factor:.1f}). Possible perimeter impact or collision."
            )
        elif rms_db >= self.sustained_db_threshold:
            classification = "SUSTAINED_LOUD_AUDIO"
            is_anomaly = True
            description = (
                f"Sustained elevated noise ({rms_db:.1f} dBFS, centroid {spectral_centroid:.0f} Hz). "
                f"Possible heavy machinery or vehicle operation nearby."
            )
        else:
            classification = "NORMAL_AMBIENT"
            is_anomaly = False
            description = f"Normal ambient border acoustic levels ({rms_db:.1f} dBFS)."

        return {
            "classification": classification,
            "rms_db": round(rms_db, 1),
            "zcr": round(zcr, 3),
            "spectral_centroid_hz": round(spectral_centroid, 1),
            "crest_factor": round(crest_factor, 2),
            "is_anomaly": is_anomaly,
            "description": description,
        }

    def generate_simulated_ambient(self, duration_sec: float = 0.5, anomaly_type: Optional[str] = None) -> np.ndarray:
        """Generates realistic synthetic border audio for test/demo environments."""
        n_samples = int(self.sample_rate * duration_sec)
        # Background wind/hiss
        ambient = np.random.normal(0, 0.008, n_samples).astype(np.float32)

        if anomaly_type == "LOUD_IMPULSE":
            # Add sudden high-amplitude pulse with exponential decay
            pulse_len = min(n_samples // 4, int(self.sample_rate * 0.04))
            decay = np.exp(-np.linspace(0, 8, pulse_len))
            freq = 900.0
            pulse = 0.95 * decay * np.sin(2 * np.pi * freq * np.arange(pulse_len) / self.sample_rate)
            start = n_samples // 4
            ambient[start:start + pulse_len] += pulse.astype(np.float32)
        elif anomaly_type == "SUSTAINED_LOUD":
            # Add loud rumbling engine sound (120 Hz + harmonics, continuous energy)
            t = np.arange(n_samples) / self.sample_rate
            engine = 0.35 * (np.sin(2 * np.pi * 120 * t) + 0.4 * np.sin(2 * np.pi * 240 * t))
            ambient += engine.astype(np.float32)

        return np.clip(ambient, -1.0, 1.0)



audio_detector = ClassicalAudioDetector()

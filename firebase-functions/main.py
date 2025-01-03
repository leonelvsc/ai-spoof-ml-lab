from firebase_functions import storage_fn, options
from google.cloud import storage, firestore, aiplatform
import numpy as np
import librosa
import io

CONFIDENCE_THRESHOLD = 0.78

# Initialize Firestore
db = firestore.Client()

# Constants
PROJECT_ID = "your_project"
ENDPOINT_ID = "some_endpoint_id"
REGION = "us-central1"
FIRESTORE_COLLECTION = "audio_predictions"

# Helper function to calculate safe float
def safe_float(value):
    return None if np.isnan(value) or np.isinf(value) else float(value)

# Firebase function triggered by storage file upload
@storage_fn.on_object_finalized(timeout_sec=300, memory=options.MemoryOption.GB_2, cpu=4)
def process_audio(event: storage_fn.CloudEvent[storage_fn.StorageObjectData]):
    # Parse event data for file details
    bucket_name = event.data.bucket
    file_name = event.data.name

    # Initialize Google Cloud Storage client and read audio file
    storage_client = storage.Client()
    bucket = storage_client.get_bucket(bucket_name)
    blob = bucket.get_blob(file_name)
    audio_bytes = blob.download_as_bytes()
    audio_stream = io.BytesIO(audio_bytes)

    # Load and process audio file
    audio, sr = librosa.load(audio_stream, sr=22050)
    window_length = 2 * sr  # 2-second windows
    num_windows = len(audio) // window_length

    # Extract audio features for each 2-second window
    doc_ref = db.collection(FIRESTORE_COLLECTION).document(file_name)

    vertex_client = aiplatform.gapic.PredictionServiceClient(client_options={
        "api_endpoint": f"{REGION}-aiplatform.googleapis.com"
    })

    endpoint = vertex_client.endpoint_path(
        project=PROJECT_ID, location=REGION, endpoint=ENDPOINT_ID
    )

    results = []

    for i in range(num_windows):
        start = i * window_length
        end = start + window_length
        window = audio[start:end]

        # Compute features
        mfcc = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13).flatten().tolist()
        mfcc_delta = librosa.feature.delta(mfcc).flatten().tolist()
        mfcc_delta2 = librosa.feature.delta(mfcc, order=2).flatten().tolist()

        snr = safe_float(10 * np.log10(np.sum(window ** 2) / np.sum((window - np.mean(window)) ** 2)))

        if snr is None:
            continue

        features = {
            "chroma_stft": safe_float(np.mean(librosa.feature.chroma_stft(y=window, sr=sr))),
            "rmse": safe_float(np.mean(librosa.feature.rms(y=window))),
            "spectral_centroid": safe_float(np.mean(librosa.feature.spectral_centroid(y=window, sr=sr))),
            "spectral_bandwidth": safe_float(np.mean(librosa.feature.spectral_bandwidth(y=window, sr=sr))),
            "rolloff": safe_float(np.mean(librosa.feature.spectral_rolloff(y=window, sr=sr))),
            "zero_crossing_rate": safe_float(np.mean(librosa.feature.zero_crossing_rate(y=window))),
            "mfcc": mfcc,
            "mfcc_delta": mfcc_delta,
            "mfcc_delta2": mfcc_delta2,
            "snr": snr,
            "spectral_contrast": librosa.feature.spectral_contrast(y=window, sr=sr).mean(axis=1).tolist(),
            "spectral_flatness": safe_float(np.mean(librosa.feature.spectral_flatness(y=window))),
        }

        response = vertex_client.predict(endpoint=endpoint, instances=[features])

        response_dict = type(response).to_dict(response)

        # Extrae las puntuaciones de bonafide y spoof
        spoof_score = response_dict["predictions"][0]["scores"][1]

        results.append(spoof_score >= CONFIDENCE_THRESHOLD)

    spoof_count = sum(results)
    total_windows = len(results)

    if total_windows <= 10:
        threshold = 0.5
    else:
        threshold = 0.6

    # Save averages to Firestore (in the parent document or another field)
    doc_ref.set({
        "spoof_count": spoof_count,
        "total_windows": total_windows,
        "prediction": "bonafide" if spoof_count / total_windows < threshold else "spoof"
    })
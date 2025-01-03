import apache_beam as beam
from apache_beam.io.gcp.gcsfilesystem import GCSFileSystem
from apache_beam.options.pipeline_options import PipelineOptions, GoogleCloudOptions, SetupOptions
import librosa
import numpy as np
import io

def run(argv=None):
    # Configuración de opciones de pipeline
    pipeline_options = PipelineOptions(flags=argv)
    google_cloud_options = pipeline_options.view_as(GoogleCloudOptions)
    google_cloud_options.project = 'your_porject'
    google_cloud_options.job_name = 'audio-spectrogram-processing'
    google_cloud_options.region = 'us-central1'
    google_cloud_options.staging_location = 'gs://your_bucket/staging'
    google_cloud_options.temp_location = 'gs://your_bucket/temp'
    pipeline_options.view_as(SetupOptions).save_main_session = True

    # Initialize GCS file system
    fs = GCSFileSystem(pipeline_options)

    def safe_float(value):
        """Returns None if the value is NaN or infinity, otherwise returns the value."""
        if np.isnan(value) or np.isinf(value):
            return None
        return value

    def filter_existing_files(file_path, label):
        # if label != 'bonafide':
        #     return False

        file_path = f"gs://your_bucket/datalake/avspoof2019/audios/{file_path}.flac"
        if fs.exists(file_path):
            return True
        return False

    class ProcessAudio(beam.DoFn):
        def setup(self):
            self.fs = GCSFileSystem(pipeline_options)

        def process(self, element):
            file_path, label = element
            audio_bytes = self.fs.open(file_path).read()
            audio_stream = io.BytesIO(audio_bytes)

            # Load audio file
            audio, sr = librosa.load(audio_stream, sr=22050)
            window_length = 2 * sr  # 2 seconds
            num_windows = len(audio) // window_length  # Number of 2-second windows

            for i in range(num_windows):
                start = i * window_length
                end = start + window_length
                window = audio[start:end]

                # Compute features for the 2-second window
                mfcc = librosa.feature.mfcc(y=window, sr=sr, n_mfcc=13)
                mfcc_delta = librosa.feature.delta(mfcc)
                mfcc_delta2 = librosa.feature.delta(mfcc, order=2)

                chroma_stft = np.mean(librosa.feature.chroma_stft(y=window, sr=sr))
                rmse = np.mean(librosa.feature.rms(y=window))
                spectral_centroid = np.mean(librosa.feature.spectral_centroid(y=window, sr=sr))
                spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(y=window, sr=sr))
                rolloff = np.mean(librosa.feature.spectral_rolloff(y=window, sr=sr))
                zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(y=window))

                # Calculate additional features
                snr = 10 * np.log10(np.sum(window ** 2) / np.sum((window - np.mean(window)) ** 2))
                spectral_contrast = np.mean(librosa.feature.spectral_contrast(y=window, sr=sr), axis=1)
                spectral_flatness = np.mean(librosa.feature.spectral_flatness(y=window))

                if safe_float(snr.astype(np.float64)) is None:
                    continue

                # Yield features as a new row for each 2-second window
                yield {
                    "chroma_stft": safe_float(chroma_stft.astype(np.float64)),
                    "rmse": safe_float(rmse.astype(np.float64)),
                    "spectral_centroid": safe_float(spectral_centroid.astype(np.float64)),
                    "spectral_bandwidth": safe_float(spectral_bandwidth.astype(np.float64)),
                    "rolloff": safe_float(rolloff.astype(np.float64)),
                    "zero_crossing_rate": safe_float(zero_crossing_rate.astype(np.float64)),
                    "mfcc": mfcc.flatten().tolist(),
                    "mfcc_delta": mfcc_delta.flatten().tolist(),
                    "mfcc_delta2": mfcc_delta2.flatten().tolist(),
                    "snr": safe_float(snr.astype(np.float64)),
                    "spectral_contrast": spectral_contrast.tolist(),
                    "spectral_flatness": safe_float(spectral_flatness.astype(np.float64)),
                    "label": label
                }

    with beam.Pipeline(options=pipeline_options) as p:
        # Leer el archivo de texto y extraer la segunda columna y la etiqueta
        audio_data = (
                p
                | 'ReadTextFile' >> beam.io.ReadFromText("gs://your_bucket/datalake/avspoof2019/metadata/PA-keys-full/keys/PA/CM/trial_metadata.txt")
                | 'ExtractColumns' >> beam.Map(lambda line: line.split())
                | 'FilterExistingFiles' >> beam.Filter(lambda fields: filter_existing_files(fields[1], fields[9]))
                | 'BuildPathAndLabel' >> beam.Map(lambda fields: (
                    f"gs://your_bucket/datalake/avspoof2019/audios/{fields[1]}.flac",  # Ruta de archivo
                    fields[9]  # Etiqueta (e.g., bonafide)
                ))
        )

        audio_data2 = (
                p
                | 'ReadTextFile2' >> beam.io.ReadFromText("gs://your_bucket/datalake/avspoof2019/metadata/DF-keys-full/keys/DF/CM/trial_metadata.txt")
                | 'ExtractColumns2' >> beam.Map(lambda line: line.split())
                | 'FilterExistingFiles2' >> beam.Filter(lambda fields: filter_existing_files(fields[1], fields[5]))
                | 'BuildPathAndLabel2' >> beam.Map(lambda fields: (
                    f"gs://your_bucket/datalake/avspoof2019/audios/{fields[1]}.flac",  # Ruta de archivo
                    fields[5]  # Etiqueta (e.g., bonafide)
                ))
        )

        combined_audio_data = (audio_data, audio_data2) | 'MergeAudioData' >> beam.Flatten()

        # Procesar el archivo de audio y extraer características
        processed_audio = (
                combined_audio_data
                | 'ProcessAudio' >> beam.ParDo(ProcessAudio())
        )

        # Volcar los datos a BigQuery
        processed_audio | 'WriteToBigQuery' >> beam.io.WriteToBigQuery(
            table='your_project:audio_training_data.audio_features_fixed_2seg',
            schema={
                'fields': [
                    {'name': 'chroma_stft', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'rmse', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'spectral_centroid', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'spectral_bandwidth', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'rolloff', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'zero_crossing_rate', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'mfcc', 'type': 'FLOAT', 'mode': 'REPEATED'},
                    {'name': 'mfcc_delta', 'type': 'FLOAT', 'mode': 'REPEATED'},
                    {'name': 'mfcc_delta2', 'type': 'FLOAT', 'mode': 'REPEATED'},
                    {'name': 'snr', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'spectral_contrast', 'type': 'FLOAT', 'mode': 'REPEATED'},
                    {'name': 'spectral_flatness', 'type': 'FLOAT', 'mode': 'NULLABLE'},
                    {'name': 'label', 'type': 'STRING', 'mode': 'NULLABLE'},
                ]
            },
            write_disposition=beam.io.BigQueryDisposition.WRITE_TRUNCATE
        )

if __name__ == '__main__':
    run()

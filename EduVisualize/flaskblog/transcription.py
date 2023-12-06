# transcription.py
import speech_recognition as sr
import math
import moviepy.editor as mp
# def extract_audio(video_path, audio_path):
#     video = mp.VideoFileClip(video_path)
#     audio = video.audio
#     audio.write_audiofile(audio_path, codec='pcm_s16le')
#     video.close()
#     audio.close()

# def split_audio(audio_path, chunk_duration):
#     recognizer = sr.Recognizer()

#     with sr.AudioFile(audio_path) as source:
#         audio = recognizer.record(source)

#     sample_rate = audio.sample_rate
#     chunk_size = int(chunk_duration * sample_rate)

#     num_chunks = math.ceil(len(audio.frame_data) / chunk_size)

#     chunks = []
#     for i in range(num_chunks):
#         start_frame = i * chunk_size
#         end_frame = min((i + 1) * chunk_size, len(audio.frame_data))
#         chunk = audio.frame_data[start_frame:end_frame]
#         chunks.append(sr.AudioData(chunk, sample_rate=sample_rate, sample_width=audio.sample_width))

#     return chunks

# def process_chunks(chunks):
#     recognizer = sr.Recognizer()
#     transcription = []

#     for idx, chunk in enumerate(chunks):
#         try:
#             text = recognizer.recognize_google(chunk)
#             transcription.append(f"{text}")
#         except sr.UnknownValueError:
#             transcription.append(f"[music]\n")
#         except sr.RequestError as e:
#             transcription.append(f"Chunk {idx + 1}: Error in the request to Google Web Speech API: {e}\n")

#     return transcription

def extract_audio_segment(video_path, audio_path, start_time, end_time):
    video = mp.VideoFileClip(video_path)
    audio = video.audio.subclip(start_time, end_time)
    audio.write_audiofile(audio_path, codec='pcm_s16le')
    video.close()
    audio.close()

def transcribe_audio(audio_path):
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_path) as source:
        audio = recognizer.record(source)

    try:
        text = recognizer.recognize_google(audio)
        return text
    except sr.UnknownValueError:
        return "[music]"
    except sr.RequestError as e:
        return f"Error in the request to Google Web Speech API: {e}"
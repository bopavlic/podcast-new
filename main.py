# filepath: /Users/borna/Documents/borna_projects/podcast-new/main.py
from moviepy.editor import (AudioFileClip, ColorClip, CompositeVideoClip,
                            TextClip, VideoFileClip) # VideoFileClip is correctly part of this import
import whisper # Added import for Whisper
import os # Already imported below, but good to have at top if used globally
import time # For potential delays
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs # New import for the main client
from elevenlabs import Voice, VoiceSettings # Voice and VoiceSettings are often here or under elevenlabs.types

from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from instagrapi import Client
from instagrapi.types import Usertag, Location

# Load environment variables from .env file
load_dotenv()

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "EXAVITQu4vr4xnSDxMaL") # Default voice if not set
INSTAGRAM_USERNAME = os.getenv("INSTAGRAM_USERNAME")
INSTAGRAM_PASSWORD = os.getenv("INSTAGRAM_PASSWORD")

# API key for ElevenLabs is now typically passed when initializing the client, so direct set_api_key might not be needed at global scope
# if ELEVENLABS_API_KEY:
#     set_api_key(ELEVENLABS_API_KEY) # This might be deprecated or handled by client
# else:
#     print("ElevenLabs API key not found. Please set it in your .env file.")

# YouTube specific constants
CLIENT_SECRETS_FILE = "client_secret.json" # Make sure this file is in the same directory
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
API_SERVICE_NAME = "youtube"
API_VERSION = "v3"

def text_to_speech_elevenlabs(text, output_path="generated_audio.mp3"):
    """
    Converts text to speech using ElevenLabs API and saves it to a file.
    """
    if not ELEVENLABS_API_KEY:
        print("Cannot generate audio: ElevenLabs API key is not set.")
        return False
    
    try:
        # Initialize the ElevenLabs client with your API key
        client = ElevenLabs(
            api_key=ELEVENLABS_API_KEY
        )
        print(f"Generating audio with ElevenLabs for text: '{text[:50]}...'")
        
        # Define voice settings
        # You can adjust these values as needed
        voice_settings_obj = VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0, 
            use_speaker_boost=True,
            speed=1.1  # Speed of speech (1.0 is normal speed)
        )

        # Generate audio using the client's text_to_speech.stream method
        audio_stream = client.text_to_speech.stream(
            text=text,
            voice_id=ELEVENLABS_VOICE_ID,
            model_id="eleven_multilingual_v2", # Or other models like "eleven_mono_v1", "eleven_turbo_v2"
            voice_settings=voice_settings_obj
        )

        # Write the audio stream to a file
        with open(output_path, "wb") as f:
            for chunk in audio_stream:
                if chunk:
                    f.write(chunk)
        print(f"Audio successfully saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error generating audio with ElevenLabs: {e}")
        return False

def get_youtube_credentials():
    """Gets valid user credentials from storage or runs the OAuth2 flow."""
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS_FILE):
                print(f"ERROR: YouTube client secrets file ('{CLIENT_SECRETS_FILE}') not found.")
                print("Please download it from Google Cloud Console and place it in the script's directory.")
                return None
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return creds

def upload_to_youtube(video_path, title, description, tags, privacy_status="public", made_for_kids=False):
    """Uploads a video to YouTube."""
    try:
        print(f"Attempting to upload '{video_path}' to YouTube...")
        credentials = get_youtube_credentials()
        if not credentials:
            print("Could not get YouTube credentials. Skipping upload.")
            return False

        youtube = build(API_SERVICE_NAME, API_VERSION, credentials=credentials)

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags,
                "categoryId": "22"  # People & Blogs. Check YouTube API for other category IDs.
            },
            "status": {
                "privacyStatus": privacy_status,
                "madeForKids": made_for_kids,
                "selfDeclaredMadeForKids": made_for_kids
            }
        }

        media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
        
        request = youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media
        )
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                print(f"Uploaded {int(status.progress() * 100)}%")
        
        print(f"YouTube upload successful! Video ID: {response.get('id')}")
        print(f"Watch it here: https://www.youtube.com/watch?v={response.get('id')}")
        return True
    except Exception as e:
        print(f"An error occurred during YouTube upload: {e}")
        return False

def upload_to_instagram_reel(video_path, caption, first_comment=""):
    """Uploads a video to Instagram as a Reel."""
    if not INSTAGRAM_USERNAME or not INSTAGRAM_PASSWORD:
        print("Instagram username or password not found in .env file. Skipping Instagram upload.")
        return False

    cl = Client()
    try:
        print("Attempting to log in to Instagram...")
        # Check for session file
        session_file = "instagram_session.json"
        if os.path.exists(session_file):
            cl.load_settings(session_file)
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD) # Verifies session
            print("Instagram session loaded from file.")
        else:
            cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            cl.dump_settings(session_file) # Save session for next time
            print("Logged in to Instagram and session saved.")

        print(f"Uploading '{video_path}' to Instagram Reels...")
        media = cl.video_upload(
            path=video_path,
            caption=caption,
            # For Reels, it's usually uploaded as a standard video post that appears in the Reels tab.
            # The differentiation is often by aspect ratio and content style.
            # To explicitly make it a reel, you might need to use a different endpoint if available
            # or ensure it's treated as such by Instagram's backend.
            # The `upload_video` method with a 9:16 aspect ratio video is standard for Reels.
            # Adding usertags or location if needed:
            # usertags=[Usertag(user=cl.user_info_by_username("someuser"), x=0.5, y=0.5)],
            # location=Location(name="Some Place", lat=40.7128, lng=-74.0060)
        )
        print(f"Instagram Reel upload successful! Media ID: {media.id}")
        if first_comment:
            cl.media_comment(media.id, first_comment)
            print(f"Added first comment: {first_comment}")
        return True
    except Exception as e:
        print(f"An error occurred during Instagram upload: {e}")
        if "login_required" in str(e).lower() and os.path.exists(session_file):
            print("Instagram login session might be invalid. Deleting session file and try again.")
            os.remove(session_file)
        return False

def transcribe_audio_to_segments(audio_path):
    """
    Transcribes the audio file using Whisper and returns segments tailored for
    word-by-word or small group display.
    """
    print(f"Loading Whisper model and transcribing: {audio_path}")
    # You can choose different models like "tiny", "base", "small", "medium", "large"
    # Smaller models are faster but less accurate. "base" is a good starting point.
    model_name = "base"
    try:
        model = whisper.load_model(model_name)
    except Exception as e:
        print(f"Error loading Whisper model '{model_name}': {e}")
        print("Please ensure openai-whisper is installed correctly and the model can be downloaded.")
        print("You might need to run: pip install openai-whisper")
        print("Also, ensure ffmpeg is installed and in your PATH.")
        return []

    try:
        # Crucially, enable word_timestamps
        print("Starting transcription with word-level timestamps...")
        result = model.transcribe(audio_path, verbose=False, word_timestamps=True)
        print("Transcription API call finished.")
    except Exception as e:
        print(f"Error during transcription: {e}")
        return []

    # --- Parameters for grouping words into subtitles ---
    # Max words to join in a single subtitle line
    MAX_WORDS_PER_SUBTITLE = 1 # Changed from 3 to 1 for single word display
    # Max duration for a single subtitle line (in seconds)
    MAX_DURATION_PER_SUBTITLE = 2.0
    # If the gap between words is larger than this (in seconds), force a new subtitle
    MIN_GAP_TO_FORCE_SPLIT = 0.3

    all_words_with_timing = []
    if 'segments' in result:
        for segment_info in result['segments']:
            if 'words' in segment_info:
                for word_data in segment_info['words']:
                    text = word_data.get('word', '').strip()
                    if text and 'start' in word_data and 'end' in word_data:
                        all_words_with_timing.append({
                            'text': text,
                            'start': float(word_data['start']),
                            'end': float(word_data['end'])
                        })
                    # else:
                        # print(f"Debug: Skipping word_data due to missing text or timestamps: {word_data}")
            # else:
                # print(f"Debug: Segment found without 'words' key: {segment_info.get('text', 'N/A')}")
    else:
        print("Error: No 'segments' key in transcription result. Cannot extract words.")
        return []

    if not all_words_with_timing:
        print("Transcription complete, but no words with timestamps could be extracted.")
        return []
    
    # print(f"Debug: Extracted {len(all_words_with_timing)} individual words with timestamps.")

    # Group words into final subtitle segments
    final_segments = []
    if not all_words_with_timing:
        return final_segments

    current_sub_words_list = []
    current_sub_start_time = 0
    current_sub_end_time = 0

    for i, word_info in enumerate(all_words_with_timing):
        if not current_sub_words_list: # Starting a new subtitle segment
            current_sub_words_list.append(word_info['text'])
            current_sub_start_time = word_info['start']
            current_sub_end_time = word_info['end']
        else:
            # Check if adding this word would violate conditions
            potential_num_words = len(current_sub_words_list) + 1
            potential_duration = word_info['end'] - current_sub_start_time
            gap_since_last_word = word_info['start'] - current_sub_end_time

            if (potential_num_words <= MAX_WORDS_PER_SUBTITLE and
                potential_duration <= MAX_DURATION_PER_SUBTITLE and
                gap_since_last_word < MIN_GAP_TO_FORCE_SPLIT):
                # Add word to current subtitle segment
                current_sub_words_list.append(word_info['text'])
                current_sub_end_time = word_info['end']
            else:
                # Finalize the current subtitle segment
                final_segments.append({
                    'text': " ".join(current_sub_words_list),
                    'start': current_sub_start_time,
                    'end': current_sub_end_time
                })
                # Start a new subtitle segment with the current word
                current_sub_words_list = [word_info['text']]
                current_sub_start_time = word_info['start']
                current_sub_end_time = word_info['end']

    # Add the last accumulated subtitle segment
    if current_sub_words_list:
        final_segments.append({
            'text': " ".join(current_sub_words_list),
            'start': current_sub_start_time,
            'end': current_sub_end_time
        })

    if not final_segments:
        print("No subtitle segments were generated after grouping words.")
    else:
        print(f"Transcription and word grouping complete. Generated {len(final_segments)} subtitle segments.")
    return final_segments

def create_styled_subtitle_video(audio_path, segments, output_path="output_video.mp4", video_size=(1080, 1920), background_video_path=None):
    """
    Creates a video with styled, synchronized subtitles.

    Args:
        audio_path (str): Path to the audio file.
        segments (list): A list of dictionaries, where each dictionary represents a subtitle segment.
                         Each dict should have 'text' (str), 'start' (float), and 'end' (float) keys.
                         Example: [{'text': 'HELLO', 'start': 0.5, 'end': 1.0}, ...]
        output_path (str): Path to save the output video file.
        video_size (tuple): (width, height) of the output video. Default is 1080x1920 for shorts/reels.
        background_video_path (str, optional): Path to a background video file. Defaults to None (solid color).
    """
    audio_clip = AudioFileClip(audio_path)
    video_duration = audio_clip.duration

    if background_video_path:
        print(f"Using background video: {background_video_path}")
        # Ensure the background video is at least as long as the audio
        # If shorter, it will loop. If longer, it will be cut.
        background_clip = VideoFileClip(background_video_path).subclip(0, video_duration)
        # Resize background to target video_size, cropping if necessary
        background_clip = background_clip.resize(height=video_size[1]) # Resize based on height
        if background_clip.w < video_size[0]: # If width is still too small (after height resize), resize by width
             background_clip = background_clip.resize(width=video_size[0])
        background_clip = background_clip.crop(x_center=background_clip.w/2, y_center=background_clip.h/2, width=video_size[0], height=video_size[1])

    else:
        print("Using solid color background.")
        background_clip = ColorClip(size=video_size, color=(30, 30, 30), duration=video_duration) # Dark grey background

    subtitle_text_clips = []
    for seg in segments:
        text_to_display = seg['text'].upper()
        start_time = seg['start']
        end_time = seg['end']
        segment_duration = end_time - start_time

        text_clip = TextClip(
            text_to_display,
            fontsize=100,  # Adjust font size as needed
            color='white',
            font='Impact', # Ensure Impact font is available or choose another
            stroke_color='black',
            stroke_width=5,   # Adjust stroke width as needed
            method='caption',
            size=(video_size[0] * 0.85, None), # Text width is 85% of video width
            align='center'
        )

        text_clip = text_clip.set_position('center').set_duration(segment_duration).set_start(start_time)
        subtitle_text_clips.append(text_clip)

    final_video_clip = CompositeVideoClip([background_clip] + subtitle_text_clips, size=video_size)
    final_video_clip = final_video_clip.set_audio(audio_clip)

    try:
        final_video_clip.write_videofile(
            output_path,
            fps=60,
            codec='libx264',
            audio_codec='aac',
            threads=4 # Use multiple threads for faster processing if available
        )
        print(f"Video successfully saved to {output_path}")
    except Exception as e:
        print(f"Error writing video file: {e}")
        print("Please ensure FFMPEG is installed and accessible by MoviePy.")
        print("If you are using a custom font, ensure the font file path is correct or the font name is recognized.")
        print("If issues persist with text rendering (especially strokes), ensure ImageMagick is installed and configured (though MoviePy often handles this well on its own).")
    finally:
        # Release resources
        audio_clip.close()
        if background_video_path:
            background_clip.close()
        for tc in subtitle_text_clips:
            tc.close()
        if 'final_video_clip' in locals():
            final_video_clip.close()


if __name__ == '__main__':
    # --- Step 0: Get story from user ---
    print("Please paste your story below. Press Ctrl+D (Unix) or Ctrl+Z then Enter (Windows) when done:")
    story_lines = []
    while True:
        try:
            line = input()
            story_lines.append(line)
        except EOFError:
            break
    story_text = "\\n".join(story_lines)

    if not story_text.strip():
        print("No story text provided. Exiting.")
        exit()
    
    video_title = story_text.split('.')[0] # Use first sentence as title, or part of it
    if len(video_title) > 80 : video_title = video_title[:80] + "..."
    video_description_youtube = f"AI Generated Story: {video_title}\\n\\n{story_text[:200]}..."
    video_caption_instagram = f"{video_title} #AIStory #ShortStory #ReelContent"
    hashtags_youtube = ["AIStory", "ShortStory", "AutomatedVideo", "TextToSpeech"]


    # --- Step 1: Configure paths ---
    base_filename = "".join(filter(str.isalnum, video_title.lower().replace(" ", "_")))[:30]
    generated_audio_file = f"assets/audio/{base_filename}_audio.mp3"
    your_background_video = "assets/video/minecraft_gameplay.mp4" 
    output_video_file = f"output/{base_filename}_final_video.mp4"

    # Create output directories if they don't exist
    os.makedirs("output", exist_ok=True)
    os.makedirs("assets/audio", exist_ok=True)
    os.makedirs("assets/video", exist_ok=True)

    # --- Step 1b: Generate Audio from Text ---
    print("\\n--- Generating Audio ---")
    if not text_to_speech_elevenlabs(story_text, generated_audio_file):
        print("Failed to generate audio. Exiting.")
        exit()
    
    your_audio_file = generated_audio_file # Use the newly generated audio

    # Check if the audio/video paths exist
    if not os.path.exists(your_audio_file):
        print("="*50)
        print(f"IMPORTANT: Audio file not found at '{your_audio_file}'.")
        print("Please ensure the audio file exists or update the path in the script.")
        print("The script cannot proceed without the audio file for transcription.")
        print("="*50)
        exit() # Exit if audio file is crucial and not found.

    if your_background_video and not os.path.exists(your_background_video):
        print("="*50)
        print(f"IMPORTANT: Background video file not found at '{your_background_video}'.")
        print("A solid color background will be used instead.")
        print("Please ensure the video file exists or update the path in the script if you want to use it.")
        print("="*50)
        your_background_video = None # Fallback to solid color

    # --- Step 2: Transcribe audio to get subtitle segments ---
    print("Starting audio transcription process...")
    subtitle_segments = transcribe_audio_to_segments(your_audio_file)

    if not subtitle_segments:
        print("No subtitle segments were generated. Exiting.")
        exit()

    # --- Step 3: Create the video ---
    print(f"Attempting to create video with audio: {your_audio_file}")
    if your_background_video:
        print(f"Using background video: {your_background_video}")
    else:
        print("Using solid color background for video.")
    print(f"Output will be saved to: {output_video_file}")

    create_styled_subtitle_video(
        your_audio_file,
        subtitle_segments, # Use dynamically generated segments
        output_path=output_video_file,
        background_video_path=your_background_video
    )

    if not os.path.exists(output_video_file):
        print(f"Video generation failed or file not found at {output_video_file}. Skipping uploads.")
        exit()
        
    # --- Step 4: Upload to YouTube ---
    print("\\n--- Uploading to YouTube ---")
    upload_to_youtube(
        output_video_file,
        title=video_title,
        description=video_description_youtube,
        tags=hashtags_youtube,
        privacy_status="public",
        made_for_kids=False
    )

    # --- Step 5: Upload to Instagram ---
    print("\\n--- Uploading to Instagram ---")
    upload_to_instagram_reel(
        output_video_file,
        caption=video_caption_instagram,
        first_comment=f"What do you think of this? #story #Storytelling"
    )

    print("\\n--- Script Finished ---")

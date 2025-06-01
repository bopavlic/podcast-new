# filepath: /Users/borna/Documents/borna_projects/podcast-story/create_subtitle_video.py
# filepath: create_subtitle_video.py
from moviepy.editor import (AudioFileClip, ColorClip, CompositeVideoClip,
                            TextClip, VideoFileClip) # VideoFileClip is correctly part of this import
import whisper # Added import for Whisper
import os # Already imported below, but good to have at top if used globally

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
    # --- Step 1: Configure paths ---
    your_audio_file = "assets/audio/coffee_war.mp3"  # IMPORTANT: Path to your audio
    # Optional: Path to your background video (e.g., Minecraft gameplay)
    your_background_video = "assets/video/minecraft_gameplay.mp4" # IMPORTANT: Path to your background video or None
    output_video_file = "output/final_short_video.mp4" # Path for the generated video

    # Create output directory if it doesn't exist
    # import os # Moved to top
    os.makedirs("output", exist_ok=True)
    os.makedirs("assets/audio", exist_ok=True) # Ensure assets/audio also exists
    os.makedirs("assets/video", exist_ok=True)


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

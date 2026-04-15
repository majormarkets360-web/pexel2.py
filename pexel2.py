import streamlit as st
import requests
import json
import time
import random
import os
import re
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
import numpy as np
import base64
from io import BytesIO
import subprocess
import tempfile
import shutil
import hashlib
from typing import List, Dict, Any, Optional

# ---------- Page Configuration ----------
st.set_page_config(
    page_title="AI Video Creator Pro - Complete Video Generator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- Custom CSS ----------
st.markdown("""
<style>
    .stButton > button {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        padding: 12px 24px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0,0,0,0.2);
    }
    .success-badge {
        background: #10b981;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 12px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# ---------- Session State ----------
if 'video_generated' not in st.session_state:
    st.session_state.video_generated = False
if 'final_video_bytes' not in st.session_state:
    st.session_state.final_video_bytes = None
if 'generated_script' not in st.session_state:
    st.session_state.generated_script = None
if 'current_topic' not in st.session_state:
    st.session_state.current_topic = None

# ---------- Sidebar Configuration ----------
st.sidebar.title("🎬 AI Video Creator Pro")
st.sidebar.markdown("---")

with st.sidebar.expander("🔐 API Keys", expanded=True):
    pexels_api_key = st.text_input(
        "Pexels API Key", 
        type="password",
        help="Get free key from pexels.com/api",
        placeholder="Enter your Pexels API key..."
    )

with st.sidebar.expander("🎬 Video Settings", expanded=True):
    video_duration = st.slider("Video Duration", 30, 60, 60, help="Target length in seconds")
    video_quality = st.selectbox("Quality", ["720p", "1080p"], index=1)
    num_clips = st.select_slider("Number of Clips", options=[4, 6, 8], value=6, help="More clips = more variety")
    add_text_overlay = st.checkbox("Add Text Overlays", value=True)

st.sidebar.markdown("---")
st.sidebar.info("💡 **Get API Key:** pexels.com/api - It's free!")

# ---------- Core Functions ----------

def search_videos(topic: str, api_key: str, max_clips: int = 8) -> List[str]:
    """Search for videos on Pexels"""
    if not api_key:
        return []
    
    headers = {'Authorization': api_key.strip()}
    
    # Use multiple related keywords for better results
    keywords = [topic, f"{topic} stock", f"{topic} footage"]
    all_urls = []
    
    for keyword in keywords[:2]:  # Limit to avoid rate limits
        url = f'https://api.pexels.com/videos/search?query={keyword}&per_page={max_clips}&orientation=portrait'
        
        try:
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                
                for video in data.get('videos', []):
                    video_files = video.get('video_files', [])
                    
                    # Get best quality
                    target_height = 1080 if video_quality == "1080p" else 720
                    best_video = None
                    
                    for vf in video_files:
                        if vf.get('height', 0) >= target_height:
                            best_video = vf
                            break
                    
                    if not best_video and video_files:
                        best_video = video_files[0]
                    
                    if best_video and best_video.get('link'):
                        all_urls.append(best_video['link'])
        except Exception as e:
            continue
    
    # Remove duplicates and return
    unique_urls = list(dict.fromkeys(all_urls))
    return unique_urls[:max_clips]

def download_video(url: str, filepath: str) -> bool:
    """Download video with retry logic"""
    for attempt in range(2):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, stream=True, timeout=45)
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=32768):
                        f.write(chunk)
                return True
        except:
            time.sleep(1)
    return False

def generate_script(topic: str, duration: int = 60) -> Dict[str, Any]:
    """Generate video script"""
    
    # Calculate scenes
    num_scenes = 6
    scene_duration = duration // num_scenes
    
    hooks = [
        f"⚠️ STOP SCROLLING! {topic.upper()} is changing everything!",
        f"🤯 The truth about {topic} that nobody tells you...",
        f"🚨 BREAKING: {topic.upper()} just went VIRAL!",
        f"💀 99% of people don't know this about {topic}"
    ]
    
    middle_texts = [
        f"Here's what experts won't tell you about {topic}...",
        f"The data shows {topic} is growing faster than ever.",
        f"Most people get {topic} completely wrong.",
        f"This {topic} secret could change everything.",
        f"Watch closely - this is the most important part.",
        f"Why is {topic} suddenly everywhere? Here's why."
    ]
    
    ctas = [
        f"Want to master {topic}? Like and follow! 🚀",
        f"Share this with someone who needs to see it!",
        f"Comment your thoughts on {topic} below! 💬",
        f"Follow for daily {topic} insights! 🔥"
    ]
    
    scenes = []
    current_time = 0
    
    # Hook scene
    scenes.append({
        "start": current_time,
        "end": current_time + scene_duration,
        "text": random.choice(hooks)
    })
    current_time += scene_duration
    
    # Middle scenes
    for i in range(num_scenes - 2):
        scenes.append({
            "start": current_time,
            "end": current_time + scene_duration,
            "text": random.choice(middle_texts)
        })
        current_time += scene_duration
    
    # CTA scene
    scenes.append({
        "start": current_time,
        "end": duration,
        "text": random.choice(ctas)
    })
    
    return {
        "topic": topic,
        "duration": duration,
        "scenes": scenes
    }

def create_video_simple(video_paths: List[str], output_path: str, duration: int) -> bool:
    """Create video by concatenating clips"""
    
    if len(video_paths) < 2:
        return False
    
    try:
        # Create concat file
        concat_file = os.path.join(os.path.dirname(output_path), "concat_list.txt")
        with open(concat_file, 'w') as f:
            for video in video_paths:
                f.write(f"file '{video}'\n")
        
        # First, concatenate all videos
        temp_concat = output_path.replace(".mp4", "_concat.mp4")
        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat',
            '-safe', '0',
            '-i', concat_file,
            '-c', 'copy',
            temp_concat
        ]
        
        result = subprocess.run(concat_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            # Fallback: use filter complex
            return False
        
        # Then trim to exact duration
        trim_cmd = [
            'ffmpeg', '-y',
            '-i', temp_concat,
            '-t', str(duration),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-movflags', '+faststart',
            output_path
        ]
        
        result = subprocess.run(trim_cmd, capture_output=True, text=True)
        
        # Cleanup
        if os.path.exists(temp_concat):
            os.remove(temp_concat)
        if os.path.exists(concat_file):
            os.remove(concat_file)
        
        return result.returncode == 0 and os.path.exists(output_path)
        
    except Exception as e:
        st.error(f"Video creation error: {str(e)[:100]}")
        return False

def add_text_to_video(input_path: str, text: str, output_path: str) -> bool:
    """Add text overlay to video"""
    try:
        # Escape special characters
        safe_text = text.replace("'", "\\'").replace('"', '\\"').replace(":", "\\:")
        
        # Simple drawtext filter
        filter_cmd = f"drawtext=text='{safe_text}':fontcolor=white:fontsize=48:x=(w-text_w)/2:y=h-100:box=1:boxcolor=black@0.6:boxborderw=10"
        
        cmd = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vf', filter_cmd,
            '-c:a', 'copy',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0 and os.path.exists(output_path)
        
    except Exception as e:
        st.warning(f"Text overlay failed: {str(e)[:50]}")
        return False

def generate_complete_video(topic: str, api_key: str, duration: int, num_clips: int) -> Optional[bytes]:
    """Generate complete video"""
    
    temp_dir = tempfile.mkdtemp()
    downloaded_clips = []
    
    try:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Step 1: Search for videos
        status_text.text("🔍 Searching for video clips...")
        video_urls = search_videos(topic, api_key, max_clips=num_clips)
        
        if len(video_urls) < 3:
            st.error(f"Only found {len(video_urls)} clips. Need at least 3.")
            return None
        
        st.success(f"✅ Found {len(video_urls)} clips!")
        progress_bar.progress(0.2)
        
        # Step 2: Download videos
        status_text.text("📥 Downloading video clips...")
        for i, url in enumerate(video_urls[:num_clips]):
            clip_path = os.path.join(temp_dir, f"clip_{i}.mp4")
            if download_video(url, clip_path):
                downloaded_clips.append(clip_path)
            progress_bar.progress(0.2 + (i / num_clips) * 0.3)
        
        if len(downloaded_clips) < 2:
            st.error("Failed to download enough clips")
            return None
        
        # Step 3: Create video
        status_text.text("🎬 Creating video...")
        temp_video = os.path.join(temp_dir, "video.mp4")
        
        if not create_video_simple(downloaded_clips, temp_video, duration):
            st.error("Failed to create video")
            return None
        
        progress_bar.progress(0.7)
        
        # Step 4: Add text overlay if enabled
        final_video = temp_video
        
        if add_text_overlay:
            status_text.text("📝 Adding text overlay...")
            script = generate_script(topic, duration)
            overlay_text = script['scenes'][0]['text'][:50]
            
            text_video = os.path.join(temp_dir, "video_with_text.mp4")
            if add_text_to_video(temp_video, overlay_text, text_video):
                final_video = text_video
                st.session_state.generated_script = script
        
        progress_bar.progress(0.9)
        
        # Step 5: Read final video
        status_text.text("✅ Finalizing...")
        
        if os.path.exists(final_video) and os.path.getsize(final_video) > 0:
            with open(final_video, 'rb') as f:
                video_bytes = f.read()
            
            progress_bar.progress(1.0)
            status_text.text("✅ Video ready!")
            
            return video_bytes
        
        return None
        
    except Exception as e:
        st.error(f"Generation error: {str(e)}")
        return None
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
        except:
            pass
        time.sleep(0.5)

# ---------- Main UI ----------

# Header
st.markdown("""
<div style="text-align: center; padding: 20px;">
    <h1>🎬 AI Video Creator Pro</h1>
    <p style="font-size: 18px; color: #667eea;">Generate complete 60-second videos automatically</p>
</div>
""", unsafe_allow_html=True)

# Main content
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    # Topic selection
    st.markdown("### 🎯 Select Your Topic")
    
    # Quick topic buttons
    quick_topics = [
        "AI Technology", "Digital Marketing", "Fitness Motivation",
        "Success Mindset", "Crypto News", "Productivity Hacks"
    ]
    
    topic_cols = st.columns(3)
    for i, topic in enumerate(quick_topics):
        with topic_cols[i % 3]:
            if st.button(f"🔥 {topic}", key=f"quick_{i}", use_container_width=True):
                st.session_state.current_topic = topic
                st.rerun()
    
    # Custom topic
    custom_topic = st.text_input(
        "Or enter your own topic:",
        placeholder="e.g., Space exploration, Digital art, Mental health"
    )
    
    if custom_topic:
        st.session_state.current_topic = custom_topic
    
    # Display selected topic
    if st.session_state.current_topic:
        st.success(f"✅ **Selected:** {st.session_state.current_topic}")
        
        if not pexels_api_key:
            st.error("⚠️ Please enter your Pexels API key in the sidebar")
        else:
            # Generate button
            if st.button("🎬 GENERATE 60-SECOND VIDEO", type="primary", use_container_width=True):
                
                with st.spinner("🎬 Generating your video... (this takes 1-2 minutes)"):
                    video_bytes = generate_complete_video(
                        st.session_state.current_topic,
                        pexels_api_key,
                        video_duration,
                        num_clips
                    )
                
                if video_bytes:
                    st.session_state.final_video_bytes = video_bytes
                    st.session_state.video_generated = True
                    
                    # Display video
                    st.markdown("### 🎥 Your Generated Video")
                    st.video(video_bytes)
                    
                    # Download button
                    filename = f"{st.session_state.current_topic.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp4"
                    st.download_button(
                        label="📥 Download Video (MP4)",
                        data=video_bytes,
                        file_name=filename,
                        mime="video/mp4",
                        use_container_width=True
                    )
                    
                    # Display script
                    if st.session_state.generated_script:
                        with st.expander("📝 View Generated Script"):
                            for scene in st.session_state.generated_script['scenes']:
                                st.markdown(f"**⏱️ {scene['start']:.0f}-{scene['end']:.0f}s**")
                                st.write(f"📖 {scene['text']}")
                                st.markdown("---")
                    
                    # Success message
                    st.balloons()
                    st.markdown("""
                    <div style="background: linear-gradient(135deg, #10b981 0%, #059669 100%); 
                                border-radius: 10px; padding: 20px; text-align: center;">
                        <h3 style="color: white;">🎉 Video Generated Successfully!</h3>
                        <p style="color: white;">Your 60-second video is ready to download and share!</p>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.error("❌ Failed to generate video. Please try again with a different topic.")
    
    # Help section
    with st.expander("ℹ️ How It Works"):
        st.markdown("""
        1. **Get your free Pexels API key** from pexels.com/api
        2. **Enter the key** in the sidebar
        3. **Select a topic** (trending or custom)
        4. **Click Generate** and wait 1-2 minutes
        5. **Download** your complete 60-second MP4 video
        
        **Requirements:**
        - Pexels API key (free)
        - Internet connection
        - FFmpeg (auto-installed on Streamlit Cloud)
        """)

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #666; padding: 20px;">
    <p>🎬 <strong>AI Video Creator Pro</strong> | Complete 60-Second Video Generation</p>
    <p style="font-size: 12px;">Powered by Pexels + FFmpeg | Creates ready-to-share MP4 videos</p>
</div>
""", unsafe_allow_html=True)

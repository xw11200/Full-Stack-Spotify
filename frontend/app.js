const DEFAULT_API = "http://127.0.0.1:8000";
const origin = window.location.origin || "";
const API_URL = origin.startsWith("http") ? origin : DEFAULT_API;

const state = {
    songs: [],
    currentIndex: null,
    playlists: ["Beats", "Radiohead", "chi", "eng"],
    audio: null,
    lyricsCache: {}
};

document.addEventListener("DOMContentLoaded", () => {
    state.audio = document.getElementById("audio-player");
    attachAudioListeners();
    attachControlListeners();
    attachLibraryActions();
    renderPlaylists();
    loadSongs();
});

async function loadSongs() {
    const list = document.getElementById("song-list");
    try {
        const response = await fetch(`${API_URL}/songs`);
        const songs = await response.json();
        state.songs = songs;
        document.getElementById("library-count").innerText = `${songs.length} tracks`;
        if (!songs.length) {
            list.innerHTML = "<p>No songs found.</p>";
            return;
        }
        renderLibrary();
        setSong(0);
    } catch (error) {
        console.error("Error fetching songs:", error);
        list.innerHTML = "<p style='color:#ff6b6b'>Error connecting to server. Is uvicorn running?</p>";
    }
}

function renderLibrary() {
    const list = document.getElementById("song-list");
    list.innerHTML = "";
    state.songs.forEach((song, index) => {
        const item = document.createElement("div");
        item.className = "list-item" + (state.currentIndex === index ? " active" : "");
        item.textContent = `${song.title} — ${song.artist}`;
        item.onclick = () => setSong(index);
        list.appendChild(item);
    });
}

function setSong(index) {
    const song = state.songs[index];
    if (!song) return;
    state.currentIndex = index;
    renderLibrary();
    updateNowPlaying(song);
    renderLyrics(song);
    updateUpNext();
    playSong(song);
    updateStatus(`Playing: ${song.title} — ${song.artist}`);
}

function updateNowPlaying(song) {
    document.getElementById("track-title").innerText = song.title;
    document.getElementById("track-artist").innerText = song.artist;
    document.getElementById("album-art-letter").innerText = song.title.charAt(0).toUpperCase();
    loadAlbumArt(song);
}

function loadAlbumArt(song) {
    const artImg = document.getElementById("album-art-img");
    const artLetter = document.getElementById("album-art-letter");
    artImg.style.display = "none";
    artLetter.style.display = "flex";
    if (!song) return;
    const targetId = song.id.toString();
    artImg.dataset.targetId = targetId;
    artImg.onload = () => {
        if (artImg.dataset.targetId !== targetId) return;
        artImg.style.display = "block";
        artLetter.style.display = "none";
    };
    artImg.onerror = () => {
        if (artImg.dataset.targetId !== targetId) return;
        artImg.removeAttribute("src");
        artImg.style.display = "none";
        artLetter.style.display = "flex";
    };
    artImg.src = `${API_URL}/cover/${song.id}`;
}

async function renderLyrics(song) {
    const block = document.getElementById("lyrics-content");
    if (!song) {
        block.innerText = "Pick a song to load lyrics.";
        return;
    }
    if (state.lyricsCache[song.id]) {
        block.innerText = state.lyricsCache[song.id];
        return;
    }
    block.innerText = "Fetching lyrics...";
    try {
        const response = await fetch(`${API_URL}/lyrics/${song.id}`);
        if (!response.ok) {
            throw new Error(`Lyrics request failed (${response.status})`);
        }
        const data = await response.json();
        const text = data.lyrics || "Lyrics unavailable.";
        state.lyricsCache[song.id] = text;
        block.innerText = text;
    } catch (error) {
        console.error("Unable to load lyrics:", error);
        block.innerText = "Lyrics unavailable. Ensure the backend has GENIUS_API_TOKEN configured.";
    }
}

function updateUpNext() {
    const list = document.getElementById("up-next-list");
    list.innerHTML = "";
    if (state.currentIndex === null) {
        list.innerHTML = "<p>Queue will show here.</p>";
        return;
    }
    const nextSongs = state.songs.slice(state.currentIndex + 1);
    if (!nextSongs.length) {
        list.innerHTML = "<p>End of queue.</p>";
        return;
    }
    nextSongs.forEach(song => {
        const div = document.createElement("div");
        div.className = "list-item";
        div.textContent = `${song.title} — ${song.artist}`;
        list.appendChild(div);
    });
}

function renderPlaylists() {
    const list = document.getElementById("playlist-list");
    list.innerHTML = "";
    state.playlists.forEach(name => {
        const div = document.createElement("div");
        div.className = "list-item";
        div.textContent = name;
        list.appendChild(div);
    });
}

function playSong(song) {
    if (!state.audio) return;
    state.audio.src = `${API_URL}/stream/${song.id}`;
    state.audio.play().catch(() => {});
    const total = formatTime(song.duration || 0);
    document.getElementById("total-time").innerText = total;
}

function attachAudioListeners() {
    const progressFill = document.getElementById("progress-fill");
    state.audio = document.getElementById("audio-player");
    state.audio.addEventListener("timeupdate", () => {
        const current = state.audio.currentTime || 0;
        const total = state.audio.duration || (state.songs[state.currentIndex]?.duration ?? 0);
        document.getElementById("current-time").innerText = formatTime(current);
        document.getElementById("total-time").innerText = formatTime(total);
        const percent = total ? (current / total) * 100 : 0;
        progressFill.style.width = `${percent}%`;
    });
    state.audio.addEventListener("ended", () => skipTrack(1));
}

function attachControlListeners() {
    document.getElementById("btn-prev").onclick = () => skipTrack(-1);
    document.getElementById("btn-next").onclick = () => skipTrack(1);
    document.getElementById("btn-play").onclick = () => state.audio?.play();
    document.getElementById("btn-pause").onclick = () => state.audio?.pause();
    document.getElementById("btn-mini").onclick = () => alert("Mini player is a mock button in this demo.");
}

function attachLibraryActions() {
    const importBtn = document.getElementById("btn-import-track");
    if (!importBtn) return;
    importBtn.addEventListener("click", handleLinkImport);
}

async function handleLinkImport() {
    const url = prompt("Paste a Spotify or Apple Music link to import:");
    if (!url) return;
    updateStatus("Importing track...");
    try {
        const response = await fetch(`${API_URL}/download`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
        });
        if (!response.ok) {
            let message = `Request failed (${response.status})`;
            const text = await response.text();
            if (text) {
                try {
                    const data = JSON.parse(text);
                    message = data.detail || message;
                } catch {
                    message = text;
                }
            }
            throw new Error(message);
        }
        updateStatus("Import complete! Refreshing library...");
        await loadSongs();
    } catch (error) {
        console.error("Import failed:", error);
        const message = error?.message || "Import failed. Check server logs.";
        updateStatus(message);
        alert(message);
    }
}

function skipTrack(direction) {
    if (state.currentIndex === null) return;
    let nextIndex = state.currentIndex + direction;
    if (nextIndex < 0) nextIndex = state.songs.length - 1;
    if (nextIndex >= state.songs.length) nextIndex = 0;
    setSong(nextIndex);
}

function updateStatus(text) {
    document.getElementById("status-bar").innerText = text;
}

function formatTime(seconds) {
    if (!seconds || Number.isNaN(seconds)) return "0:00";
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60).toString().padStart(2, "0");
    return `${mins}:${secs}`;
}

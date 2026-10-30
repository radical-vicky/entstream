
/* ============================================================
   STREAMSPHERE - LIVE STREAM VIEWER
   LiveKit Client SDK 2.x

   HTML elements expected:
   watchRoot
   watchVideo
   watchPlaceholder
   watchConnectionStatus
   watchViewerCount

   Django data attributes:
   data-token-url
   data-livekit-url
   data-stream-id
   data-live
============================================================ */

(() => {
    "use strict";

    const LIVEKIT_SDK_URL =
        "https://cdn.jsdelivr.net/npm/livekit-client@2.15.6/+esm";

    let room = null;
    let livekit = null;
    let isConnecting = false;
    let isDestroyed = false;

    let videoElement = null;
    let placeholder = null;
    let connectionLabel = null;
    let root = null;

    const attachedAudioElements = new Set();

    function getElements() {
        root = document.getElementById("watchRoot");
        videoElement = document.getElementById("watchVideo");
        placeholder = document.getElementById("watchPlaceholder");
        connectionLabel = document.getElementById(
            "watchConnectionStatus"
        );

        if (!root || !videoElement) {
            console.error(
                "StreamSphere Viewer: Required player elements are missing."
            );
            return false;
        }

        return true;
    }

    function updateStatus(message, connected = false) {
        if (!connectionLabel) return;

        connectionLabel.textContent = message;

        const statusContainer = connectionLabel.parentElement;
        const dot = statusContainer
            ? statusContainer.querySelector(".watch-connection-dot")
            : null;

        if (dot) {
            dot.style.background = connected
                ? "#20c77a"
                : "#9299a4";
        }
    }

    function showPlaceholder(title, message) {
        if (!placeholder) return;

        placeholder.style.display = "flex";

        const heading = placeholder.querySelector("h3");
        const description = placeholder.querySelector("p");

        if (heading) heading.textContent = title;
        if (description) description.textContent = message;
    }

    function hidePlaceholder() {
        if (placeholder) {
            placeholder.style.display = "none";
        }
    }

    function getTokenUrl() {
        return root.dataset.tokenUrl || "";
    }

    function getLiveKitUrl() {
        return (
            root.dataset.livekitUrl ||
            ""
        ).trim();
    }

    function isStreamLive() {
        return root.dataset.live === "true";
    }

    async function getAccessToken() {
        const tokenUrl = getTokenUrl();

        if (!tokenUrl) {
            throw new Error("The LiveKit token URL is missing.");
        }

        const response = await fetch(tokenUrl, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            }
        });

        let data;

        try {
            data = await response.json();
        } catch (error) {
            throw new Error(
                "The token endpoint did not return valid JSON."
            );
        }

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.detail ||
                `Token request failed (${response.status}).`
            );
        }

        const token =
            data.token ||
            data.access_token ||
            data.livekit_token;

        if (!token) {
            throw new Error(
                data.error ||
                "The server did not provide a LiveKit access token."
            );
        }

        return {
            token: token,
            url:
                data.livekit_url ||
                data.url ||
                getLiveKitUrl()
        };
    }

    function attachVideoTrack(track) {
        if (!videoElement || !track) return;

        try {
            track.attach(videoElement);

            videoElement.autoplay = true;
            videoElement.playsInline = true;
            videoElement.muted = false;

            videoElement.play().catch((error) => {
                console.warn(
                    "StreamSphere: Browser blocked automatic video playback.",
                    error
                );

                updateStatus("Click play to watch");
            });

            hidePlaceholder();
            updateStatus("Connected", true);

        } catch (error) {
            console.error(
                "StreamSphere: Could not attach remote video.",
                error
            );
        }
    }

    function attachAudioTrack(track) {
        if (!track) return;

        try {
            const audioElement = track.attach();

            audioElement.autoplay = true;
            audioElement.controls = false;

            document.body.appendChild(audioElement);
            attachedAudioElements.add(audioElement);

            audioElement.play().catch((error) => {
                console.warn(
                    "StreamSphere: Audio autoplay was blocked.",
                    error
                );
            });

        } catch (error) {
            console.error(
                "StreamSphere: Could not attach remote audio.",
                error
            );
        }
    }

    function detachTrack(track) {
        if (!track) return;

        try {
            const elements = track.detach();

            elements.forEach((element) => {
                if (
                    element instanceof HTMLAudioElement &&
                    element.parentNode
                ) {
                    element.parentNode.removeChild(element);
                    attachedAudioElements.delete(element);
                }
            });

        } catch (error) {
            console.warn(
                "StreamSphere: Track detach warning.",
                error
            );
        }
    }

    function clearAudioElements() {
        attachedAudioElements.forEach((element) => {
            if (element.parentNode) {
                element.parentNode.removeChild(element);
            }
        });

        attachedAudioElements.clear();
    }

    function registerRoomEvents() {
        if (!room || !livekit) return;

        const {
            RoomEvent,
            Track,
            ConnectionState
        } = livekit;

        room.on(RoomEvent.TrackSubscribed, (track, publication, participant) => {
            console.log(
                "StreamSphere: Track subscribed.",
                publication.kind,
                participant.identity
            );

            if (publication.kind === Track.Kind.Video) {
                attachVideoTrack(track);
            }

            if (publication.kind === Track.Kind.Audio) {
                attachAudioTrack(track);
            }
        });

        room.on(RoomEvent.TrackUnsubscribed, (track) => {
            detachTrack(track);

            const hasVideo = room.remoteParticipants
                ? Array.from(room.remoteParticipants.values()).some(
                    participant => Array.from(
                        participant.videoTrackPublications.values()
                    ).some(publication => publication.track)
                )
                : false;

            if (!hasVideo) {
                showPlaceholder(
                    "Video temporarily unavailable",
                    "Waiting for the creator's video signal."
                );
            }
        });

        room.on(RoomEvent.ParticipantConnected, (participant) => {
            console.log(
                "StreamSphere: Creator or participant joined.",
                participant.identity
            );
        });

        room.on(RoomEvent.ParticipantDisconnected, (participant) => {
            console.log(
                "StreamSphere: Participant disconnected.",
                participant.identity
            );
        });

        room.on(RoomEvent.Connected, () => {
            console.log("StreamSphere: Connected to LiveKit.");
            updateStatus("Connected", true);

            if (room.remoteParticipants.size === 0) {
                showPlaceholder(
                    "Waiting for the creator",
                    "You are connected. The broadcast will appear when the creator starts sending video."
                );
            }
        });

        room.on(RoomEvent.Disconnected, (reason) => {
            console.warn(
                "StreamSphere: Disconnected from LiveKit.",
                reason
            );

            updateStatus("Disconnected");

            showPlaceholder(
                "Connection lost",
                "Your connection to the live stream was interrupted."
            );
        });

        room.on(RoomEvent.Reconnecting, () => {
            updateStatus("Reconnecting");

            showPlaceholder(
                "Reconnecting...",
                "Trying to restore your live stream connection."
            );
        });

        room.on(RoomEvent.Reconnected, () => {
            console.log("StreamSphere: Reconnected.");
            updateStatus("Connected", true);
        });

        room.on(RoomEvent.ConnectionStateChanged, (state) => {
            console.log(
                "StreamSphere: Connection state:",
                state
            );

            if (state === ConnectionState.Reconnecting) {
                updateStatus("Reconnecting");
            }
        });

        room.on(RoomEvent.MediaDevicesError, (error) => {
            console.warn(
                "StreamSphere: Media device warning.",
                error
            );
        });
    }

    async function connectToStream() {
        if (isConnecting || isDestroyed) return;

        if (!isStreamLive()) {
            updateStatus("Offline");

            showPlaceholder(
                "This stream is not live",
                "The creator is not broadcasting at the moment."
            );

            return;
        }

        isConnecting = true;

        updateStatus("Connecting");

        showPlaceholder(
            "Connecting to stream",
            "Please wait while StreamSphere connects you to the broadcast."
        );

        try {
            console.log("StreamSphere: Loading LiveKit SDK...");

            livekit = await import(LIVEKIT_SDK_URL);

            if (isDestroyed) return;

            const credentials = await getAccessToken();

            if (isDestroyed) return;

            if (!credentials.url) {
                throw new Error(
                    "LiveKit server URL is missing. Check LIVEKIT_URL in Django settings."
                );
            }

            console.log("StreamSphere: Creating viewer room...");

            room = new livekit.Room({
                adaptiveStream: true,
                dynacast: true
            });

            registerRoomEvents();

            console.log("StreamSphere: Connecting to LiveKit...");

            await room.connect(
                credentials.url,
                credentials.token,
                {
                    autoSubscribe: true
                }
            );

            if (isDestroyed) {
                await room.disconnect();
                return;
            }

            console.log(
                "StreamSphere: Viewer connected successfully."
            );

            updateStatus("Connected", true);

            /*
             * If the creator published before this viewer joined,
             * inspect existing publications and attach subscribed tracks.
             */
            room.remoteParticipants.forEach((participant) => {
                participant.trackPublications.forEach((publication) => {
                    if (!publication.track) return;

                    if (
                        publication.kind === livekit.Track.Kind.Video
                    ) {
                        attachVideoTrack(publication.track);
                    }

                    if (
                        publication.kind === livekit.Track.Kind.Audio
                    ) {
                        attachAudioTrack(publication.track);
                    }
                });
            });

            if (
                room.remoteParticipants.size === 0 ||
                !videoElement.srcObject
            ) {
                showPlaceholder(
                    "Waiting for the creator",
                    "You are connected. Video will appear as soon as the creator publishes their camera."
                );
            }

        } catch (error) {
            console.error(
                "StreamSphere Viewer connection error:",
                error
            );

            updateStatus("Connection failed");

            showPlaceholder(
                "Unable to connect",
                error.message ||
                "We could not connect you to this live broadcast. Please refresh and try again."
            );

        } finally {
            isConnecting = false;
        }
    }

    async function disconnectViewer() {
        isDestroyed = true;

        try {
            if (room) {
                await room.disconnect();
                room = null;
            }

            if (videoElement) {
                videoElement.pause();
                videoElement.srcObject = null;
            }

            clearAudioElements();

        } catch (error) {
            console.warn(
                "StreamSphere: Viewer cleanup warning.",
                error
            );
        }
    }

    function initializeViewer() {
        if (!getElements()) return;

        if (!isStreamLive()) {
            updateStatus("Offline");

            showPlaceholder(
                "This stream is not live",
                "The creator is not broadcasting at the moment."
            );

            return;
        }

        connectToStream();

        /*
         * Clean up when the viewer leaves or refreshes the page.
         */
        window.addEventListener("pagehide", disconnectViewer, {
            once: true
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initializeViewer,
            { once: true }
        );
    } else {
        initializeViewer();
    }

})();

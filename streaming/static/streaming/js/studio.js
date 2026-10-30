(() => {
    "use strict";

    const root = document.querySelector("#studioPreview[data-stream-id]");

    if (!root) return;

    // =====================================================
    // STREAM CONFIGURATION
    // =====================================================

    const streamId = root.dataset.streamId;
    const tokenUrl = root.dataset.tokenUrl;
    const startUrl = root.dataset.startUrl;
    const endUrl = root.dataset.endUrl;
    const livekitUrl = root.dataset.livekitUrl;
    const broadcastType = root.dataset.broadcastType || "browser";

    const preview = document.querySelector("#studioPreview");
    const video = document.querySelector("#studioVideo");
    const placeholder = document.querySelector("#studioPlaceholder");

    const enableCameraBtn = document.querySelector("#studioEnableCamera");
    const goLiveBtn = document.querySelector("#studioGoLive");
    const stopLiveBtn = document.querySelector("#studioStopLive");

    const message = document.querySelector("#studioMessage");
    const errorBox = document.querySelector("#studioError");

    const statusDot = document.querySelector("#studioStatusDot");
    const statusText = document.querySelector("#studioStatusText");

    const viewerCount = document.querySelector("#studioViewerCount");

    // =====================================================
    // STATE
    // =====================================================

    let room = null;
    let cameraStream = null;
    let LiveKitRoom = null;
    let Track = null;

    let isLive = statusText?.textContent.trim().toLowerCase() === "live";
    let isConnecting = false;
    let isStopping = false;

    // =====================================================
    // UI HELPERS
    // =====================================================

    function showMessage(text) {
        if (message) {
            message.textContent = text;
        }
    }

    function showError(text) {
        console.error("[StreamSphere Studio]", text);

        if (errorBox) {
            errorBox.textContent = text;
            errorBox.hidden = false;
        } else {
            showMessage(text);
        }
    }

    function clearError() {
        if (errorBox) {
            errorBox.textContent = "";
            errorBox.hidden = true;
        }
    }

    function setBusy(button, busy, busyText) {
        if (!button) return;

        if (busy) {
            if (!button.dataset.originalText) {
                button.dataset.originalText = button.textContent.trim();
            }

            button.disabled = true;

            if (busyText) {
                button.textContent = busyText;
            }
        } else {
            button.disabled = false;

            if (button.dataset.originalText) {
                button.textContent = button.dataset.originalText;
                delete button.dataset.originalText;
            }
        }
    }

    function setStatus(status) {
        const normalized = status.toLowerCase();

        if (statusText) {
            statusText.textContent = status;
        }

        if (statusDot) {
            statusDot.classList.toggle("live", normalized === "live");
        }

        isLive = normalized === "live";
    }

    function updateControls() {
        if (goLiveBtn) {
            goLiveBtn.hidden = isLive;
            goLiveBtn.disabled = !cameraStream || isConnecting || isStopping;
        }

        if (stopLiveBtn) {
            stopLiveBtn.hidden = !isLive;
            stopLiveBtn.disabled = isConnecting || isStopping;
        }

        if (enableCameraBtn) {
            // We allow enabling camera even if we are "live" in the database
            // so the user can see their preview.
            enableCameraBtn.disabled = isConnecting || isStopping;
        }
    }

    function showPreview() {
        if (placeholder) {
            placeholder.hidden = true;
            placeholder.style.display = "none"; // Force hide
        }

        if (video) {
            video.hidden = false;
            video.style.display = "block"; // Force show
        }

        if (preview) {
            preview.hidden = false;
        }
    }

    function showPlaceholder() {
        if (placeholder) {
            placeholder.hidden = false;
            placeholder.style.display = "flex"; // Restore display
        }
    }

    // =====================================================
    // CSRF AND REQUEST HELPERS
    // =====================================================

    function getCookie(name) {
        const cookie = document.cookie
            .split(";")
            .map(item => item.trim())
            .find(item => item.startsWith(name + "="));

        if (!cookie) return "";

        return decodeURIComponent(
            cookie.substring(name.length + 1)
        );
    }

    async function postJSON(url, data = {}) {
        if (!url) {
            throw new Error("The required server endpoint is missing.");
        }

        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(data)
        });

        const result = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                result.error ||
                result.message ||
                `Server request failed (${response.status}).`
            );
        }

        return result;
    }

    // =====================================================
    // LIVEKIT
    // =====================================================

    async function loadLiveKit() {
        if (LiveKitRoom && Track) {
            return;
        }

        try {
            const livekit = await import(
                "https://cdn.jsdelivr.net/npm/livekit-client@2.15.6/+esm"
            );

            LiveKitRoom = livekit.Room;
            Track = livekit.Track;

            if (!LiveKitRoom || !Track) {
                throw new Error("LiveKit client could not be initialized.");
            }
        } catch (error) {
            throw new Error(
                "Could not load the LiveKit broadcasting library. Check your internet connection and try again."
            );
        }
    }

    async function getToken() {
        if (!tokenUrl) {
            throw new Error("The broadcast token URL is missing.");
        }

        const response = await fetch(tokenUrl, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "X-Requested-With": "XMLHttpRequest"
            }
        });

        const data = await response.json().catch(() => ({}));

        if (!response.ok) {
            throw new Error(
                data.error ||
                data.message ||
                `Could not obtain a broadcast token (${response.status}).`
            );
        }

        if (!data.token) {
            throw new Error("The server did not return a LiveKit token.");
        }

        return data;
    }

    // =====================================================
    // CAMERA AND MICROPHONE
    // =====================================================

    async function enableCamera() {
        if (broadcastType !== "browser") {
            showMessage(
                "This stream uses OBS. Configure your OBS connection details to broadcast."
            );
            return;
        }

        // Removed the `isLive` check here so we can always preview the camera
        if (isConnecting) return;

        clearError();

        setBusy(
            enableCameraBtn,
            true,
            "Enabling camera..."
        );

        try {
            if (!navigator.mediaDevices?.getUserMedia) {
                throw new Error(
                    "Camera access is unavailable. Use HTTPS or localhost and check your browser permissions."
                );
            }

            // Release any previous camera session.
            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
                cameraStream = null;
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    frameRate: { ideal: 30 }
                },
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            cameraStream = stream;

            if (video) {
                video.srcObject = cameraStream;
                video.muted = true;
                video.playsInline = true;
                
                // Force the video to be visible and on top
                video.style.display = "block";
                video.style.zIndex = "10";

                await video.play().catch(() => {});
            }

            showPreview();

            showMessage(
                "Camera and microphone are ready. You can now go live."
            );

            updateControls();

        } catch (error) {
            showError(
                error.message ||
                "Could not access your camera or microphone."
            );

            if (cameraStream) {
                cameraStream.getTracks().forEach(track => track.stop());
                cameraStream = null;
            }

            updateControls();

        } finally {
            setBusy(enableCameraBtn, false);
            updateControls();
        }
    }

    // =====================================================
    // CONNECT TO LIVEKIT AND PUBLISH
    // =====================================================

    async function connectAndPublish() {
        await loadLiveKit();

        const credentials = await getToken();

        const serverUrl = credentials.url || livekitUrl;

        if (!serverUrl) {
            throw new Error(
                "The LiveKit server URL is missing. Check your Django settings."
            );
        }

        if (!cameraStream) {
            throw new Error(
                "Enable your camera and microphone before going live."
            );
        }

        const videoTrack = cameraStream.getVideoTracks()[0];
        const audioTrack = cameraStream.getAudioTracks()[0];

        if (!videoTrack && !audioTrack) {
            throw new Error(
                "No active camera or microphone tracks were found."
            );
        }

        room = new LiveKitRoom({
            adaptiveStream: true,
            dynacast: true
        });

        room.on("disconnected", () => {
            if (isLive) {
                showMessage(
                    "Your connection to the broadcast server was interrupted."
                );
            }
        });

        await room.connect(serverUrl, credentials.token);

        if (videoTrack) {
            await room.localParticipant.publishTrack(videoTrack, {
                source: Track.Source.Camera
            });
        }

        if (audioTrack) {
            await room.localParticipant.publishTrack(audioTrack, {
                source: Track.Source.Microphone
            });
        }

        return credentials;
    }

    // =====================================================
    // START BROADCAST
    // =====================================================

    async function startBroadcast() {
        if (broadcastType !== "browser") {
            showMessage(
                "Use your OBS connection details to start this broadcast."
            );
            return;
        }

        if (isConnecting) return;

        clearError();

        if (!cameraStream) {
            showError(
                "Please enable your camera and microphone first."
            );
            return;
        }

        isConnecting = true;
        updateControls();

        setBusy(
            goLiveBtn,
            true,
            "Starting broadcast..."
        );

        try {
            // First connect to LiveKit and publish media.
            await connectAndPublish();

            // Then tell Django that the stream is live.
            await postJSON(startUrl);

            setStatus("Live");

            showMessage(
                "You are now live! Your audience can watch your broadcast."
            );

            updateControls();

        } catch (error) {
            showError(
                error.message ||
                "Could not start your broadcast."
            );

            if (room) {
                try {
                    await room.disconnect();
                } catch (disconnectError) {
                    console.error(disconnectError);
                }

                room = null;
            }

            setStatus("Not live");

        } finally {
            isConnecting = false;
            setBusy(goLiveBtn, false);
            updateControls();
        }
    }

    // =====================================================
    // END BROADCAST
    // =====================================================

    async function stopBroadcast() {
        if (!isLive || isStopping) return;

        clearError();

        isStopping = true;
        updateControls();

        setBusy(
            stopLiveBtn,
            true,
            "Ending stream..."
        );

        try {
            // Notify Django to end the stream.
            await postJSON(endUrl);

            // Disconnect the LiveKit room.
            if (room) {
                await room.disconnect();
                room = null;
            }

            setStatus("Ended");

            showMessage(
                "Your broadcast has ended successfully."
            );

            // Keep the camera preview available.
            updateControls();

        } catch (error) {
            showError(
                error.message ||
                "Could not end your broadcast."
            );

        } finally {
            isStopping = false;
            setBusy(stopLiveBtn, false);
            updateControls();
        }
    }

    // =====================================================
    // OBS MODE
    // =====================================================

    function initializeOBS() {
        if (enableCameraBtn) {
            enableCameraBtn.hidden = true;
        }

        if (goLiveBtn) {
            goLiveBtn.hidden = true;
        }

        if (isLive) {
            showMessage("Your OBS stream is marked as live.");
        } else {
            showMessage(
                "OBS mode selected. Use the OBS connection details to configure your broadcast."
            );
        }

        updateControls();
    }

    // =====================================================
    // OBS COPY BUTTONS
    // =====================================================

    function initializeCopyButtons() {
        document.querySelectorAll("[data-copy-target]").forEach(button => {
            button.addEventListener("click", async () => {
                const targetId = button.dataset.copyTarget;
                const input = document.getElementById(targetId);

                if (!input) return;

                const originalText = button.textContent.trim();

                try {
                    await navigator.clipboard.writeText(input.value);

                } catch (error) {
                    const previousType = input.type;

                    input.type = "text";
                    input.removeAttribute("readonly");
                    input.select();

                    const copied = document.execCommand("copy");

                    input.setAttribute("readonly", "readonly");
                    input.type = previousType;

                    if (!copied) {
                        showError("Could not copy the connection details.");
                        return;
                    }
                }

                button.textContent = "Copied";

                window.setTimeout(() => {
                    button.textContent = originalText;
                }, 1500);
            });
        });
    }

    // =====================================================
    // CLEANUP
    // =====================================================

    function cleanup() {
        if (room) {
            room.disconnect().catch(error => {
                console.error("LiveKit cleanup error:", error);
            });

            room = null;
        }

        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
        }

        if (video) {
            video.srcObject = null;
        }
    }

    // =====================================================
    // INITIALIZATION
    // =====================================================

    if (broadcastType === "browser") {
        enableCameraBtn?.addEventListener("click", enableCamera);
        goLiveBtn?.addEventListener("click", startBroadcast);
        stopLiveBtn?.addEventListener("click", stopBroadcast);

        // If the database says we are already live, we still want to let the user preview their camera
        if (isLive) {
            if (enableCameraBtn) enableCameraBtn.disabled = false; 
            if (goLiveBtn) goLiveBtn.hidden = true;
            if (stopLiveBtn) stopLiveBtn.hidden = false;
            showMessage("This stream is already live. Click 'Enable camera' to see your preview.");
        } else {
            updateControls();
            showMessage("Enable your camera and microphone to prepare your broadcast.");
        }

    } else if (broadcastType === "obs") {
        initializeOBS();
        stopLiveBtn?.addEventListener("click", stopBroadcast);
    }

    initializeCopyButtons();
    window.addEventListener("beforeunload", cleanup);

})();
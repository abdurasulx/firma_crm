/* Sahifa ICHIDA (getUserMedia) ishlaydigan kamera vidjeti — modal orqali. */
(function () {
    let activeField = null;   // hozir modal orqali to'ldirilayotgan .camera-field elementi
    let stream = null;

    const modal = document.getElementById('cameraCaptureModal');
    if (!modal) return;  // sahifada camera_capture_widget.html include qilinmagan

    const video = modal.querySelector('.camera-video');
    const canvas = modal.querySelector('.camera-canvas');
    const previewImg = modal.querySelector('.camera-preview');
    const placeholder = modal.querySelector('.camera-placeholder');
    const statusEl = modal.querySelector('.camera-status');
    const shootBtn = modal.querySelector('.btn-camera-shoot');
    const retakeBtn = modal.querySelector('.btn-camera-retake');
    const acceptBtn = modal.querySelector('.btn-camera-accept');
    const titleEl = document.getElementById('cameraModalTitle');

    function setStatus(text) {
        if (statusEl) statusEl.textContent = text || '';
    }

    function showLive() {
        video.style.display = 'block';
        previewImg.style.display = 'none';
        placeholder.style.display = 'none';
        shootBtn.style.display = '';
        retakeBtn.style.display = 'none';
        acceptBtn.style.display = 'none';
    }

    function showCaptured() {
        video.style.display = 'none';
        previewImg.style.display = 'block';
        placeholder.style.display = 'none';
        shootBtn.style.display = 'none';
        retakeBtn.style.display = '';
        acceptBtn.style.display = '';
    }

    function showPlaceholder(text) {
        video.style.display = 'none';
        previewImg.style.display = 'none';
        placeholder.style.display = 'flex';
        placeholder.querySelector('span').textContent = text || 'Kamera ochilmoqda...';
        shootBtn.style.display = 'none';
        retakeBtn.style.display = 'none';
        acceptBtn.style.display = 'none';
    }

    function stopStream() {
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
    }

    function startStream(facingMode) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            showPlaceholder('Bu brauzerda kamera qo‘llab-quvvatlanmaydi.');
            return;
        }
        showPlaceholder('Kamera ochilmoqda...');
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: facingMode || 'environment' },
            audio: false,
        }).then(function (s) {
            stream = s;
            video.srcObject = s;
            showLive();
            setStatus('');
        }).catch(function () {
            showPlaceholder('Kameraga ruxsat berilmadi.');
        });
    }

    function setFieldFile(fieldEl, file) {
        const realInput = fieldEl.querySelector('.camera-real-input');
        const dt = new DataTransfer();
        dt.items.add(file);
        realInput.files = dt.files;
        realInput.dispatchEvent(new Event('change', { bubbles: true }));

        const thumbImg = fieldEl.querySelector('.camera-thumb-img');
        const thumbPlaceholder = fieldEl.querySelector('.camera-thumb-placeholder');
        thumbImg.src = URL.createObjectURL(file);
        thumbImg.style.display = 'block';
        if (thumbPlaceholder) thumbPlaceholder.style.display = 'none';
        const openBtn = fieldEl.querySelector('.btn-camera-open');
        if (openBtn) openBtn.textContent = 'Qayta olish';
    }

    window.closeCameraCaptureModal = function () {
        modal.style.display = 'none';
        stopStream();
        activeField = null;
    };

    function openCameraModalFor(fieldEl) {
        activeField = fieldEl;
        titleEl.textContent = fieldEl.dataset.label || 'Rasmga olish';
        modal.style.display = 'flex';
        startStream(fieldEl.dataset.facing || 'environment');
    }

    shootBtn.addEventListener('click', function () {
        if (!video.videoWidth) return;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(function (blob) {
            if (!blob) return;
            previewImg.src = URL.createObjectURL(blob);
            showCaptured();
            stopStream();
        }, 'image/jpeg', 0.9);
    });

    retakeBtn.addEventListener('click', function () {
        if (activeField) startStream(activeField.dataset.facing || 'environment');
    });

    acceptBtn.addEventListener('click', function () {
        if (!activeField || !previewImg.src) return;
        fetch(previewImg.src).then(function (r) { return r.blob(); }).then(function (blob) {
            const filename = (activeField.dataset.filename || 'photo') + '.jpg';
            setFieldFile(activeField, new File([blob], filename, { type: 'image/jpeg' }));
            window.closeCameraCaptureModal();
        });
    });

    document.querySelectorAll('[data-camera-field]').forEach(function (fieldEl) {
        const openBtn = fieldEl.querySelector('.btn-camera-open');
        if (openBtn) {
            openBtn.addEventListener('click', function () { openCameraModalFor(fieldEl); });
        }
    });
})();

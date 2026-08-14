/*
 * Sahifa ICHIDA (getUserMedia orqali) ishlaydigan kamera vidjeti.
 *
 * Real bug (server logi orqali tasdiqlangan): oldingi yondashuvda
 * <input type="file" capture> orqali iOS'ning tashqi Kamera ilovasi
 * ochilardi — bu Safari'ni fonga surib qo'yardi, va rasm olib
 * qaytgandan keyin ba'zan tanlangan fayl "yaroqsiz" holatga tushib
 * qolar edi: forma yuborilganda butun so'rov tanasi BO'SH (Content-
 * Length: 0) ketib, "CSRF token missing" kabi tushunarsiz xato berardi
 * (aslida CSRF bilan bog'liq emas edi — WebKit darajasidagi xato).
 *
 * Bu vidjet kamerani sahifaning O'ZIDA (getUserMedia + <video> +
 * <canvas>) ochadi — hech qachon Safari'dan/sahifadan chiqmaydi,
 * shuning uchun bu muammo butunlay oldini oladi.
 */
function setupCameraWidget(rootEl, opts) {
    opts = opts || {};
    const video = rootEl.querySelector('.camera-video');
    const canvas = rootEl.querySelector('.camera-canvas');
    const previewImg = rootEl.querySelector('.camera-preview');
    const placeholder = rootEl.querySelector('.camera-placeholder');
    const shootBtn = rootEl.querySelector('.btn-camera-shoot');
    const galleryBtn = rootEl.querySelector('.btn-camera-gallery');
    const retakeBtn = rootEl.querySelector('.btn-camera-retake');
    const galleryInput = rootEl.querySelector('.camera-gallery-input');
    const realInput = rootEl.querySelector('.camera-real-input');
    const statusEl = rootEl.querySelector('.camera-status');
    let stream = null;

    function setStatus(text) {
        if (statusEl) statusEl.textContent = text || '';
    }

    function showLive() {
        video.style.display = 'block';
        previewImg.style.display = 'none';
        if (placeholder) placeholder.style.display = 'none';
        retakeBtn.style.display = 'none';
    }

    function showPreview() {
        video.style.display = 'none';
        previewImg.style.display = 'block';
        if (placeholder) placeholder.style.display = 'none';
        retakeBtn.style.display = '';
    }

    function showPlaceholder() {
        video.style.display = 'none';
        previewImg.style.display = 'none';
        if (placeholder) placeholder.style.display = 'flex';
        shootBtn.style.display = 'none';
        retakeBtn.style.display = 'none';
    }

    function stopStream() {
        if (stream) {
            stream.getTracks().forEach(function (t) { t.stop(); });
            stream = null;
        }
    }

    function startStream() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            // Eski/nostandart brauzer — faqat galereya bilan ishlaydi.
            setStatus('Bu brauzerda jonli kamera qo‘llab-quvvatlanmaydi — Galereyadan tanlang.');
            showPlaceholder();
            return;
        }
        setStatus('Kamera ochilmoqda...');
        navigator.mediaDevices.getUserMedia({
            video: { facingMode: opts.facingMode || 'environment' },
            audio: false,
        }).then(function (s) {
            stream = s;
            video.srcObject = s;
            showLive();
            shootBtn.style.display = '';
            setStatus('');
        }).catch(function () {
            setStatus('Kameraga ruxsat berilmadi — Galereyadan tanlang.');
            showPlaceholder();
        });
    }

    function setFileFromBlob(blob, filename) {
        const file = new File([blob], filename, { type: blob.type || 'image/jpeg' });
        const dt = new DataTransfer();
        dt.items.add(file);
        realInput.files = dt.files;
        realInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    shootBtn.addEventListener('click', function () {
        if (!video.videoWidth) return;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        canvas.getContext('2d').drawImage(video, 0, 0);
        canvas.toBlob(function (blob) {
            if (!blob) return;
            previewImg.src = URL.createObjectURL(blob);
            showPreview();
            setFileFromBlob(blob, (opts.filename || 'photo') + '.jpg');
            stopStream();
        }, 'image/jpeg', 0.9);
    });

    retakeBtn.addEventListener('click', function () {
        startStream();
    });

    galleryBtn.addEventListener('click', function () {
        galleryInput.click();
    });

    galleryInput.addEventListener('change', function () {
        const file = galleryInput.files && galleryInput.files[0];
        if (!file) return;
        previewImg.src = URL.createObjectURL(file);
        showPreview();
        stopStream();
        const dt = new DataTransfer();
        dt.items.add(file);
        realInput.files = dt.files;
        realInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    startStream();
}

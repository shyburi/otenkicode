const API_BASE_URL = 'http://127.0.0.1:5001/api';

// DOM要素の取得
const authSection = document.getElementById('auth-section');
const logoutSection = document.getElementById('logout-section');
const welcomeMessage = document.getElementById('welcome-message');
const clothSection = document.getElementById('cloth-section');
const outfitSection = document.getElementById('outfit-section');
const clothesListSection = document.getElementById('clothes-list-section');

// ---------------- 認証状態の管理 ----------------
function checkLoginStatus() {
    const token = localStorage.getItem('access_token');
    if (token) {
        authSection.classList.add('hidden');
        logoutSection.classList.remove('hidden');
        clothSection.classList.remove('hidden');
        outfitSection.classList.remove('hidden');
        clothesListSection.classList.remove('hidden');
        // ユーザー情報を表示するロジック（バックエンドにユーザー名を取得するAPIが必要）
        welcomeMessage.textContent = 'ユーザー'; // 仮の表示
        return true;
    } else {
        authSection.classList.remove('hidden');
        logoutSection.classList.add('hidden');
        clothSection.classList.add('hidden');
        outfitSection.classList.add('hidden');
        clothesListSection.classList.add('hidden');
        return false;
    }
}

// ---------------- 認証済みリクエストのヘルパー関数 ----------------
async function fetchWithAuth(url, options = {}) {
    const token = localStorage.getItem('access_token');
    console.log('Stored token:', token);
    
    if (!token) {
        alert('ログインしてください。');
        window.location.reload();
        return;
    }

    // headersオプションが存在しない場合、空のオブジェクトで初期化
    if (!options.headers) {
        options.headers = {};
    }

    // Authorizationヘッダーを追加
    options.headers['Authorization'] = `Bearer ${token}`;
    console.log('Request headers:', options.headers);

    return fetch(url, options);
}

// ---------------- 服の登録フォーム ----------------
document.getElementById('cloth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submit-btn');
    const analysisStatus = document.getElementById('analysis-status');
    
    // ボタンを無効化し、分析中表示を表示
    submitBtn.disabled = true;
    submitBtn.textContent = 'AI分析中...';
    analysisStatus.style.display = 'block';
    
    const formData = new FormData(e.target);

    // フォームデータの内容をコンソールに出力（デバッグ用）
    console.log('Form data being sent:');
    for (let [key, value] of formData.entries()) {
        console.log(key, value);
    }

    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/clothes`, {
            method: 'POST',
            body: formData,
        });
        
        if (response) {
            const result = await response.json();
            console.log('Response:', result);
            console.log('Status:', response.status);
            
            if (response.ok) {
                alert(result.message || '服の登録が完了しました！');
                e.target.reset(); // フォームをリセット
            } else {
                if (response.status === 503) {
                    alert(`⚠️ ${result.error}\n\nAPI制限のため、しばらく待ってから再試行してください。`);
                } else {
                    alert(`エラー (${response.status}): ${result.error || '不明なエラーが発生しました'}`);
                }
            }
        }
    } catch (error) {
        console.error('Request failed:', error);
        alert('リクエストに失敗しました: ' + error.message);
    } finally {
        // ボタンを有効化し、分析中表示を非表示
        submitBtn.disabled = false;
        submitBtn.textContent = 'AI分析して登録';
        analysisStatus.style.display = 'none';
    }
});

// ---------------- 新規登録フォーム ----------------
document.getElementById('register-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('register-name').value;
    const email = document.getElementById('register-email').value;
    const password = document.getElementById('register-password').value;

    const response = await fetch(`${API_BASE_URL}/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password })
    });

    const result = await response.json();
    alert(result.message || result.msg);
});

// ---------------- ログインフォーム ----------------
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('login-email').value;
    const password = document.getElementById('login-password').value;

    const response = await fetch(`${API_BASE_URL}/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password })
    });

    if (response.ok) {
        const result = await response.json();
        console.log('Login response:', result);
        localStorage.setItem('access_token', result.access_token);
        console.log('Token saved:', result.access_token);
        alert('ログイン成功！');
        checkLoginStatus(); // 状態を更新
    } else {
        const result = await response.json();
        alert(result.msg || 'ログインに失敗しました。');
    }
});

// ---------------- ログアウトボタン ----------------
document.getElementById('logout-button').addEventListener('click', () => {
    localStorage.removeItem('access_token');
    alert('ログアウトしました。');
    checkLoginStatus(); // 状態を更新
});


// ---------------- コーディネート取得ボタン ----------------
document.getElementById('get-outfit').addEventListener('click', async () => {
    const container = document.getElementById('outfit-container');
    container.innerHTML = '';
    
    function setOutfitStatus(text) {
        let statusEl = document.getElementById('outfit-status');
        if (!statusEl) {
            statusEl = document.createElement('p');
            statusEl.id = 'outfit-status';
            // outfit-container の直前に入れる
            const parent = document.getElementById('outfit-section');
            parent.insertBefore(statusEl, container);
        }
        statusEl.textContent = text;
    }

    async function fetchAndRenderOutfit(url) {
        const response = await fetchWithAuth(url);
        if (!response) return;
        const outfit = await response.json();
        if (Array.isArray(outfit) && outfit.length > 0) {
            outfit.forEach(item => {
                const imgContainer = document.createElement('div');
                imgContainer.classList.add('cloth-item');

                const img = document.createElement('img');
                img.src = `${API_BASE_URL.replace('/api', '')}/static/${item.image_path}`;

                imgContainer.appendChild(img);
                container.appendChild(imgContainer);
            });
        } else {
            container.innerHTML = '<p>提案できるコーディネートが見つかりませんでした。</p>';
        }
    }

    // Geolocation APIで現在地を取得
    if (navigator.geolocation) {
        const highAccuracyOptions = { enableHighAccuracy: true, timeout: 8000, maximumAge: 0 };
        const relaxedOptions = { enableHighAccuracy: false, timeout: 15000, maximumAge: 600000 };

        navigator.geolocation.getCurrentPosition(async (position) => {
            const lat = position.coords.latitude;
            const lon = position.coords.longitude;
            console.log(`Current position: Latitude ${lat}, Longitude ${lon}`);
            setOutfitStatus(`現在地: 緯度 ${lat.toFixed(5)}, 経度 ${lon.toFixed(5)}`);
            // 緯度・経度をクエリパラメータとして追加してAPIを呼び出す
            await fetchAndRenderOutfit(`${API_BASE_URL}/outfit?lat=${lat}&lon=${lon}`);
        }, async (error) => {
            console.error("Geolocation error (high accuracy): ", error);
            if (error && (error.code === 2 || error.code === 3)) {
                // 一度だけ緩いオプションで再試行
                navigator.geolocation.getCurrentPosition(async (position2) => {
                    const lat2 = position2.coords.latitude;
                    const lon2 = position2.coords.longitude;
                    console.log(`Retry position: Latitude ${lat2}, Longitude ${lon2}`);
                    setOutfitStatus(`現在地(再試行): 緯度 ${lat2.toFixed(5)}, 経度 ${lon2.toFixed(5)}`);
                    await fetchAndRenderOutfit(`${API_BASE_URL}/outfit?lat=${lat2}&lon=${lon2}`);
                }, async (error2) => {
                    console.error("Geolocation error (relaxed): ", error2);
                    alert("現在地の取得に失敗しました。デフォルトのコーディネートを提案します。");
                    setOutfitStatus('現在地取得に失敗: デフォルトの天気データを使用');
                    await fetchAndRenderOutfit(`${API_BASE_URL}/outfit`);
                }, relaxedOptions);
            } else {
                alert("現在地の取得に失敗しました。デフォルトのコーディネートを提案します。");
                setOutfitStatus('現在地取得に失敗: デフォルトの天気データを使用');
                await fetchAndRenderOutfit(`${API_BASE_URL}/outfit`);
            }
        }, highAccuracyOptions);
    } else {
        alert("お使いのブラウザは位置情報サービスをサポートしていません。");
        // 位置情報が取得できない場合、パラメータなしでAPIを呼び出す
        setOutfitStatus('位置情報非対応: デフォルトの天気データを使用');
        await fetchAndRenderOutfit(`${API_BASE_URL}/outfit`);
    }
});

// ---------------- デバッグ用：JWTトークンテスト ----------------
async function testToken() {
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/debug-token`);
        if (response) {
            const result = await response.json();
            console.log('Token test result:', result);
            return result;
        }
    } catch (error) {
        console.error('Token test failed:', error);
    }
}

// ---------------- デバッグ用：手動JWTトークンテスト ----------------
async function testTokenManual() {
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/debug-token-manual`, {
            method: 'POST'
        });
        if (response) {
            const result = await response.json();
            console.log('Manual token test result:', result);
            return result;
        }
    } catch (error) {
        console.error('Manual token test failed:', error);
    }
}

// ---------------- 服一覧表示ボタン ----------------
document.getElementById('show-clothes').addEventListener('click', async () => {
    const container = document.getElementById('clothes-list-container');
    container.innerHTML = '';
    
    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/clothes`);
        if (response) {
            const clothes = await response.json();
            
            if (Array.isArray(clothes) && clothes.length > 0) {
                clothes.forEach(cloth => {
                    const clothDiv = document.createElement('div');
                    clothDiv.style.border = '1px solid #ccc';
                    clothDiv.style.padding = '10px';
                    clothDiv.style.margin = '10px 0';
                    clothDiv.style.borderRadius = '4px';
                    
                    clothDiv.innerHTML = `
                        <div style="display: flex; gap: 10px;">
                            <img src="${API_BASE_URL.replace('/api', '')}/static/${cloth.image_path}" 
                                 style="width: 100px; height: 100px; object-fit: cover; border-radius: 4px;">
                            <div>
                                <h4>${cloth.item_type || 'Unknown'}</h4>
                                <p><strong>色:</strong> ${cloth.color_name || 'Unknown'} (${cloth.color_hex || 'N/A'})</p>
                                <p><strong>パターン:</strong> ${cloth.pattern || 'Unknown'}</p>
                                <p><strong>素材:</strong> ${cloth.material || 'Unknown'}</p>
                                <p><strong>スタイル:</strong> ${cloth.style || 'Unknown'}</p>
                                <p><strong>推奨気温:</strong> ${cloth.recommended_temp || 'Unknown'}</p>
                                <p><strong>推奨湿度:</strong> ${cloth.recommended_humidity || 'Unknown'}</p>
                            </div>
                        </div>
                    `;
                    
                    container.appendChild(clothDiv);
                });
            } else {
                container.innerHTML = '<p>登録された服がありません。</p>';
            }
        }
    } catch (error) {
        console.error('Failed to fetch clothes:', error);
        container.innerHTML = '<p>服一覧の取得に失敗しました。</p>';
    }
});

// ページ読み込み時に認証状態をチェック
window.addEventListener('load', checkLoginStatus);
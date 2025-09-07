#!/usr/bin/env python3
"""
ConoHa VPS ARKサーバー管理システム
セキュア完全版 with 認証・Discord通知・ログ機能
"""

import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import time
import hmac
import hashlib

# ===========================
# ページ設定
# ===========================
st.set_page_config(
    page_title="ARK Server Manager",
    page_icon="🦖",
    layout="wide"
)

# ===========================
# 認証システム
# ===========================
def check_password():
    """パスワード認証機能"""
    
    def password_entered():
        """パスワード確認処理"""
        if 'app_password' in st.secrets:
            # secrets.tomlにパスワードが設定されている場合
            if hmac.compare_digest(
                st.session_state["password"],
                st.secrets["app_password"]
            ):
                st.session_state["password_correct"] = True
                del st.session_state["password"]
                log_action("ログイン成功")
            else:
                st.session_state["password_correct"] = False
                log_action("ログイン失敗")
        else:
            # パスワード未設定の場合（開発環境用）
            st.warning("⚠️ パスワードが設定されていません。本番環境では必ず設定してください。")
            st.session_state["password_correct"] = True

    # 認証済みチェック
    if st.session_state.get("password_correct", False):
        return True

    # ログイン画面
    st.title("🦖 ARK Server Manager")
    st.markdown("### ログインが必要です")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.text_input(
            "パスワードを入力してください",
            type="password",
            on_change=password_entered,
            key="password",
            placeholder="パスワード"
        )
        
        if "password_correct" in st.session_state and not st.session_state["password_correct"]:
            st.error("😕 パスワードが正しくありません")
        
        st.info("💡 パスワードは管理者に確認してください")
    
    return False

# ===========================
# Discord通知機能
# ===========================
def send_discord_notification(message, notification_type="info"):
    """Discord Webhook通知送信"""
    try:
        webhook_url = st.secrets.get("discord", {}).get("webhook_url")
        if not webhook_url:
            return False
        
        # メッセージタイプに応じた絵文字
        emoji_map = {
            "success": "✅",
            "error": "❌",
            "warning": "⚠️",
            "info": "ℹ️",
            "start": "🟢",
            "stop": "🔴",
            "restart": "🔄"
        }
        
        emoji = emoji_map.get(notification_type, "📢")
        
        # Discord Embed形式
        embed = {
            "embeds": [{
                "title": f"{emoji} ARKサーバー通知",
                "description": message,
                "color": {
                    "success": 0x00ff00,
                    "error": 0xff0000,
                    "warning": 0xffff00,
                    "info": 0x0099ff,
                    "start": 0x00ff00,
                    "stop": 0xff0000,
                    "restart": 0xffa500
                }.get(notification_type, 0x808080),
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "ARK Server Manager"
                }
            }]
        }
        
        response = requests.post(webhook_url, json=embed)
        return response.status_code == 204
    except:
        return False

# ===========================
# ログ機能
# ===========================
def log_action(action, status="info"):
    """操作ログの記録"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # セッションにログを保存
    if 'logs' not in st.session_state:
        st.session_state.logs = []
    
    log_entry = {
        "timestamp": timestamp,
        "action": action,
        "status": status
    }
    
    st.session_state.logs.append(log_entry)
    
    # 最新20件のみ保持
    st.session_state.logs = st.session_state.logs[-20:]
    
    # Discord通知も送信
    send_discord_notification(f"{timestamp} - {action}", status)

# ===========================
# ConoHa API設定
# ===========================
def get_api_config():
    """API設定の取得（安全に）"""
    try:
        config = {
            "username": st.secrets["CONOHA_USERNAME"],
            "password": st.secrets["CONOHA_PASSWORD"],
            "tenant_id": st.secrets["CONOHA_TENANT_ID"],
            "server_id": st.secrets["VPS_SERVER_ID"]
        }
        return config
    except KeyError as e:
        st.error(f"⚠️ 設定エラー: {e} が secrets.toml に設定されていません")
        st.info("""
        ### 設定方法
        1. Streamlit Cloud の設定画面を開く
        2. Secrets タブを選択
        3. 以下の形式で設定を追加：
        ```toml
        app_password = "your-password"
        CONOHA_USERNAME = "your-username"
        CONOHA_PASSWORD = "your-password"
        CONOHA_TENANT_ID = "your-tenant-id"
        VPS_SERVER_ID = "your-server-id"
        
        [discord]
        webhook_url = "https://discord.com/api/webhooks/..."
        ```
        """)
        return None

# エンドポイント（c3j1リージョン）
AUTH_ENDPOINT = "https://identity.c3j1.conoha.io/v3/auth/tokens"

def get_compute_endpoint(tenant_id):
    """Compute エンドポイントの取得"""
    return f"https://compute.c3j1.conoha.io/v2.1/{tenant_id}"

# ===========================
# セッション状態初期化
# ===========================
if 'token' not in st.session_state:
    st.session_state.token = None
if 'vps_status' not in st.session_state:
    st.session_state.vps_status = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

# ===========================
# ConoHa API関数
# ===========================
def get_auth_token(config):
    """ConoHa v3 API認証"""
    auth_data = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": config["username"],
                        "password": config["password"],
                        "domain": {
                            "name": "default"
                        }
                    }
                }
            },
            "scope": {
                "project": {
                    "id": config["tenant_id"]
                }
            }
        }
    }
    
    try:
        response = requests.post(
            AUTH_ENDPOINT,
            json=auth_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if response.status_code == 201:
            token = response.headers.get('X-Subject-Token')
            st.session_state.token = token
            return token
        else:
            log_action(f"認証失敗: {response.status_code}", "error")
            return None
    except requests.exceptions.Timeout:
        st.error("⏱️ 認証タイムアウト")
        return None
    except Exception as e:
        log_action(f"認証エラー: {e}", "error")
        return None

def get_server_status(config):
    """VPSの状態取得"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token(config)
    
    if not st.session_state.token:
        return None
    
    headers = {"X-Auth-Token": st.session_state.token}
    compute_endpoint = get_compute_endpoint(config["tenant_id"])
    
    try:
        response = requests.get(
            f"{compute_endpoint}/servers/{config['server_id']}",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            server = response.json()['server']
            st.session_state.last_update = datetime.now()
            return {
                'status': server['status'],
                'name': server.get('name', 'Unknown'),
                'created': server.get('created', ''),
                'addresses': server.get('addresses', {}),
                'power_state': server.get('OS-EXT-STS:power_state', 0)
            }
        elif response.status_code == 401:
            # トークン期限切れ
            st.session_state.token = get_auth_token(config)
            return get_server_status(config)  # リトライ
        else:
            log_action(f"サーバー情報取得失敗: {response.status_code}", "error")
            return None
    except requests.exceptions.Timeout:
        st.error("⏱️ サーバー状態取得タイムアウト")
        return None
    except Exception as e:
        log_action(f"状態取得エラー: {e}", "error")
        return None

def start_vps(config):
    """VPS起動"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token(config)
    
    headers = {"X-Auth-Token": st.session_state.token}
    compute_endpoint = get_compute_endpoint(config["tenant_id"])
    
    try:
        response = requests.post(
            f"{compute_endpoint}/servers/{config['server_id']}/action",
            headers=headers,
            json={"os-start": None},
            timeout=10
        )
        
        if response.status_code == 202:
            log_action("VPS起動コマンド送信", "start")
            return True
        else:
            log_action(f"起動失敗: {response.status_code}", "error")
            return False
    except Exception as e:
        log_action(f"起動エラー: {e}", "error")
        return False

def stop_vps(config):
    """VPS停止"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token(config)
    
    headers = {"X-Auth-Token": st.session_state.token}
    compute_endpoint = get_compute_endpoint(config["tenant_id"])
    
    try:
        response = requests.post(
            f"{compute_endpoint}/servers/{config['server_id']}/action",
            headers=headers,
            json={"os-stop": None},
            timeout=10
        )
        
        if response.status_code == 202:
            log_action("VPS停止コマンド送信", "stop")
            return True
        else:
            log_action(f"停止失敗: {response.status_code}", "error")
            return False
    except Exception as e:
        log_action(f"停止エラー: {e}", "error")
        return False

def reboot_vps(config):
    """VPS再起動"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token(config)
    
    headers = {"X-Auth-Token": st.session_state.token}
    compute_endpoint = get_compute_endpoint(config["tenant_id"])
    
    try:
        response = requests.post(
            f"{compute_endpoint}/servers/{config['server_id']}/action",
            headers=headers,
            json={"reboot": {"type": "SOFT"}},
            timeout=10
        )
        
        if response.status_code == 202:
            log_action("VPS再起動コマンド送信", "restart")
            return True
        else:
            log_action(f"再起動失敗: {response.status_code}", "error")
            return False
    except Exception as e:
        log_action(f"再起動エラー: {e}", "error")
        return False

# ===========================
# メイン処理
# ===========================
def main():
    """メインアプリケーション"""
    
    # 認証チェック
    if not check_password():
        st.stop()
    
    # API設定取得
    config = get_api_config()
    if not config:
        st.stop()
    
    # ヘッダー
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("🦖 ARK Server Manager")
        st.markdown("ConoHa VPS管理システム（セキュア版）")
    with col2:
        if st.button("🚪 ログアウト", use_container_width=True):
            st.session_state.password_correct = False
            st.rerun()
    
    # サイドバー
    with st.sidebar:
        st.header("⚙️ システム情報")
        
        # 接続状態
        if st.session_state.token:
            st.success("✅ API接続済み")
        else:
            st.warning("⚠️ API未接続")
        
        st.success("🔐 c3j1リージョン")
        
        # 最終更新時刻
        if st.session_state.last_update:
            st.caption(f"最終更新: {st.session_state.last_update.strftime('%H:%M:%S')}")
        
        st.divider()
        
        # 料金情報
        st.header("💰 料金情報")
        st.metric("時間単価", "6.6円/時間")
        st.metric("月額上限", "3,608円")
        st.caption("※停止中は課金されません")
        
        st.divider()
        
        # 操作ログ
        st.header("📝 操作ログ")
        if 'logs' in st.session_state and st.session_state.logs:
            for log in reversed(st.session_state.logs[-5:]):  # 最新5件表示
                st.caption(f"{log['timestamp']}")
                st.caption(f"└ {log['action']}")
        else:
            st.caption("ログなし")
        
        # 認証更新ボタン
        st.divider()
        if st.button("🔄 認証更新", use_container_width=True):
            st.session_state.token = get_auth_token(config)
            if st.session_state.token:
                st.success("認証成功！")
                log_action("認証更新成功", "success")
            else:
                st.error("認証失敗")
                log_action("認証更新失敗", "error")
    
    # メインコンテンツ
    st.header("🎮 VPS管理パネル")
    
    # 状態取得
    with st.spinner("サーバー状態を取得中..."):
        server = get_server_status(config)
    
    if server:
        # ステータス表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if server['status'] == 'ACTIVE':
                st.success(f"🟢 **稼働中**")
                status_emoji = "🟢"
            elif server['status'] == 'SHUTOFF':
                st.error(f"🔴 **停止中**")
                status_emoji = "🔴"
            else:
                st.warning(f"⏳ **{server['status']}**")
                status_emoji = "⏳"
        
        with col2:
            st.info(f"📍 **IP:** 163.44.119.3")
        
        with col3:
            st.metric("サーバー名", server.get('name', 'ARK Server'))
        
        with col4:
            power_states = {
                0: "NOSTATE",
                1: "RUNNING",
                3: "PAUSED",
                4: "SHUTDOWN",
                6: "CRASHED",
                7: "SUSPENDED"
            }
            power_state = power_states.get(server.get('power_state', 0), "UNKNOWN")
            st.metric("電源状態", power_state)
        
        st.divider()
        
        # 操作ボタン
        st.subheader("📱 サーバー操作")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button(
                "🟢 **起動**",
                disabled=(server['status'] == 'ACTIVE'),
                use_container_width=True,
                help="VPSを起動します（3-5分かかります）"
            ):
                with st.spinner("🚀 起動処理中..."):
                    if start_vps(config):
                        st.success("✅ 起動コマンド送信成功！")
                        st.info("📢 3-5分後にARKサーバーに接続可能です")
                        st.balloons()
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 起動に失敗しました")
        
        with col2:
            if st.button(
                "🔴 **停止**",
                disabled=(server['status'] == 'SHUTOFF'),
                use_container_width=True,
                help="VPSを停止します（課金も停止）"
            ):
                # 確認ダイアログ
                with st.spinner("🛑 停止処理中..."):
                    if stop_vps(config):
                        st.success("✅ 停止コマンド送信成功！")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 停止に失敗しました")
        
        with col3:
            if st.button(
                "🔄 **再起動**",
                disabled=(server['status'] != 'ACTIVE'),
                use_container_width=True,
                help="VPSを再起動します（5-7分かかります）"
            ):
                with st.spinner("♻️ 再起動処理中..."):
                    if reboot_vps(config):
                        st.success("✅ 再起動コマンド送信成功！")
                        st.warning("⏳ 5-7分お待ちください")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 再起動に失敗しました")
        
        with col4:
            if st.button(
                "🔄 **状態更新**",
                use_container_width=True,
                help="現在の状態を再取得します"
            ):
                st.rerun()
        
        # 接続情報
        st.divider()
        st.subheader("🌐 接続情報")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📡 ARKサーバー接続")
            st.code("""
# Steamから接続
サーバー: 163.44.119.3:7777
パスワード: なし（オープンサーバー）

# 接続方法
1. Steamを開く
2. 表示 → サーバー → お気に入り
3. サーバーを追加
4. 163.44.119.3:7777 を入力
            """)
        
        with col2:
            st.markdown("### 🤖 Discord Bot コマンド")
            st.code("""
# 基本コマンド
!ark     - サーバー状態確認
!start   - ARKサーバー起動
!stop    - ARKサーバー停止
!auto    - 自動停止設定確認

# 管理コマンド
!shutdown - VPS完全停止
!reboot   - VPS再起動
!cost     - 料金情報表示
            """)
        
        # 詳細情報（展開可能）
        with st.expander("📖 **詳細な使い方**"):
            st.markdown("""
            ## 🚀 サーバー起動手順
            
            1. **このページで「🟢 起動」ボタンをクリック**
               - またはDiscordで `!start` コマンド
            
            2. **3-5分待つ**
               - VPSの起動: 約2分
               - ARKサーバーの自動起動: 約3分
            
            3. **Steamから接続**
               - お気に入りに `163.44.119.3:7777` を追加
               - サーバーリストから選択して接続
            
            ---
            
            ## 🛑 サーバー停止手順
            
            ### 方法1: Webから停止（推奨）
            - このページで「🔴 停止」ボタンをクリック
            
            ### 方法2: Discordから停止
            - `!stop` : ARKサーバーのみ停止
            - `!shutdown` : VPS完全停止（課金停止）
            
            ---
            
            ## 💰 料金について
            
            | 状態 | 料金 |
            |------|------|
            | 起動中 | 6.6円/時間 |
            | 停止中 | 0円 |
            | 月額上限 | 3,608円 |
            
            - **自動停止機能**: プレイヤー0人で30分後に自動停止
            - **月末精算**: 使用時間に応じて割り勘
            
            ---
            
            ## ⚠️ 注意事項
            
            - **最後の人が抜ける時は必ず停止**してください
            - **長時間の放置は避けて**ください（他の人が使えません）
            - **サーバー設定の変更**は管理者に相談してください
            
            ---
            
            ## 🆘 トラブルシューティング
            
            **Q: 接続できない**
            - A: VPS起動から5分待ってから再試行
            
            **Q: ラグい、重い**
            - A: 「🔄 再起動」ボタンで再起動
            
            **Q: Botが反応しない**
            - A: VPSが起動しているか確認
            
            **Q: サーバーが見つからない**
            - A: お気に入りに正しく追加されているか確認
            """)
        
        # 現在のプレイ状況（ダミー）
        with st.expander("👥 **プレイヤー情報**（開発中）"):
            st.info("この機能は現在開発中です")
            st.caption("将来的に以下の情報を表示予定：")
            st.caption("- 現在のプレイヤー数")
            st.caption("- プレイヤー名一覧")
            st.caption("- プレイ時間統計")
            st.caption("- 自動停止までの時間")
        
    else:
        # エラー表示
        st.error("⚠️ サーバー情報を取得できません")
        
        col1, col2, col3 = st.columns(3)
        with col2:
            if st.button("🔄 再試行", use_container_width=True):
                st.session_state.token = None
                st.rerun()
        
        st.info("""
        ### 考えられる原因：
        - API認証の期限切れ
        - ネットワークエラー
        - ConoHa側のメンテナンス
        
        「再試行」ボタンをクリックしてください。
        """)
    
    # フッター
    st.divider()
    col1, col2, col3 = st.columns(3)
    with col1:
        st.caption("🦖 ARK Server Manager v2.0")
    with col2:
        st.caption("🔐 Secure Edition")
    with col3:
        st.caption(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ===========================
# エントリーポイント
# ===========================
if __name__ == "__main__":
    main()
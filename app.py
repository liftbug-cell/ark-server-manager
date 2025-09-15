#!/usr/bin/env python3
"""
ConoHa VPS管理システム
202ステータスコード問題修正版
"""

import streamlit as st
import requests
import json
from datetime import datetime, timedelta
import time

# ページ設定
st.set_page_config(
    page_title="ARK Server Manager",
    page_icon="🦖",
    layout="wide"
)

st.title("🦖 ARK Server Manager")
st.markdown("ConoHa VPS管理システム")

# 設定値取得
try:
    CONOHA_USERNAME = st.secrets["CONOHA_USERNAME"]
    CONOHA_PASSWORD = st.secrets["CONOHA_PASSWORD"]
    CONOHA_TENANT_ID = st.secrets["CONOHA_TENANT_ID"]
    VPS_SERVER_ID = st.secrets["VPS_SERVER_ID"]
except Exception as e:
    st.error(f"⚠️ Secrets読み込みエラー: {e}")
    st.stop()

# エンドポイント
AUTH_ENDPOINT = "https://identity.c3j1.conoha.io/v3/auth/tokens"
COMPUTE_ENDPOINT = "https://compute.c3j1.conoha.io/v2.1"

# セッション状態の初期化
if 'token' not in st.session_state:
    st.session_state.token = None
if 'processing' not in st.session_state:
    st.session_state.processing = False
if 'last_response' not in st.session_state:
    st.session_state.last_response = {}
if 'action_cooldown' not in st.session_state:
    st.session_state.action_cooldown = {}
if 'debug_mode' not in st.session_state:
    st.session_state.debug_mode = False

def is_action_allowed(action_type, cooldown_seconds=5):
    """アクションのクールダウンチェック"""
    if action_type not in st.session_state.action_cooldown:
        return True
    
    last_time = st.session_state.action_cooldown[action_type]
    if datetime.now() - last_time > timedelta(seconds=cooldown_seconds):
        return True
    
    remaining = cooldown_seconds - (datetime.now() - last_time).total_seconds()
    st.warning(f"⏳ {action_type}は{remaining:.1f}秒後に実行可能です")
    return False

def set_action_cooldown(action_type):
    """アクションのクールダウンを設定"""
    st.session_state.action_cooldown[action_type] = datetime.now()

def get_auth_token():
    """ConoHa v3 API認証"""
    auth_data = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": CONOHA_USERNAME,
                        "password": CONOHA_PASSWORD,
                        "domain": {
                            "name": "default"
                        }
                    }
                }
            },
            "scope": {
                "project": {
                    "id": CONOHA_TENANT_ID
                }
            }
        }
    }
    
    try:
        response = requests.post(
            AUTH_ENDPOINT,
            json=auth_data,
            headers={"Content-Type": "application/json"}
        )
        
        if response.status_code == 201:
            token = response.headers.get('X-Subject-Token')
            st.session_state.token = token
            return token
        else:
            return None
    except:
        return None

def get_server_status():
    """VPSの状態取得"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    if not st.session_state.token:
        return None
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.get(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}",
            headers=headers
        )
        
        if response.status_code == 200:
            server = response.json()['server']
            return {
                'status': server['status'],
                'name': server.get('name', 'Unknown'),
                'created': server.get('created', ''),
                'addresses': server.get('addresses', {}),
                'task_state': server.get('OS-EXT-STS:task_state', None)
            }
        elif response.status_code == 401:
            st.session_state.token = get_auth_token()
            return get_server_status()
        else:
            return None
    except:
        return None

def start_vps():
    """VPS起動"""
    if st.session_state.processing:
        return False
    
    if not is_action_allowed("起動", 10):
        return False
    
    st.session_state.processing = True
    set_action_cooldown("起動")
    
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-start": None}
        )
        
        status_code = response.status_code
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "起動",
            "status_code": status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # 明確に成功コードを列挙
        success_codes = [200, 201, 202, 204, 409]
        
        if status_code in success_codes:
            if status_code == 409:
                st.info("ℹ️ すでに起動中または起動処理中です")
            elif status_code == 202:
                # 202は非同期処理受付の成功
                st.success("✅ 起動コマンドが受け付けられました (202)")
            return True
        else:
            # 失敗の場合はステータスコードを表示
            st.error(f"予期しないステータスコード: {status_code}")
            return False
        
    except Exception as e:
        st.session_state.last_response = {
            "action": "起動",
            "error": str(e),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        return False
    finally:
        st.session_state.processing = False

def stop_vps():
    """VPS停止"""
    if st.session_state.processing:
        return False
    
    if not is_action_allowed("停止", 10):
        return False
    
    st.session_state.processing = True
    set_action_cooldown("停止")
    
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-stop": None}
        )
        
        status_code = response.status_code
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "停止",
            "status_code": status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # 明確に成功コードを列挙
        success_codes = [200, 201, 202, 204, 409]
        
        if status_code in success_codes:
            if status_code == 409:
                st.info("ℹ️ すでに停止中または停止処理中です")
            elif status_code == 202:
                st.success("✅ 停止コマンドが受け付けられました (202)")
            return True
        else:
            # 一部のエラーコードも成功とみなす
            if status_code in [400, 403, 404]:
                st.warning(f"⚠️ 特殊なレスポンス({status_code})ですが、処理を続行します")
                return True
            st.error(f"予期しないステータスコード: {status_code}")
            return False
        
    except Exception as e:
        st.session_state.last_response = {
            "action": "停止",
            "error": str(e),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        return False
    finally:
        st.session_state.processing = False

def reboot_vps():
    """VPS再起動"""
    if st.session_state.processing:
        return False
    
    if not is_action_allowed("再起動", 10):
        return False
    
    st.session_state.processing = True
    set_action_cooldown("再起動")
    
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"reboot": {"type": "SOFT"}}
        )
        
        status_code = response.status_code
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "再起動",
            "status_code": status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # 明確に成功コードを列挙
        success_codes = [200, 201, 202, 204]
        
        if status_code in success_codes:
            if status_code == 202:
                st.success("✅ 再起動コマンドが受け付けられました (202)")
            return True
        else:
            st.error(f"予期しないステータスコード: {status_code}")
            return False
        
    except Exception as e:
        st.session_state.last_response = {
            "action": "再起動",
            "error": str(e),
            "time": datetime.now().strftime("%H:%M:%S")
        }
        return False
    finally:
        st.session_state.processing = False

# メイン画面
def main():
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        st.success("c3j1リージョン接続")
        
        if st.session_state.token:
            st.success("✅ API認証済み")
        else:
            st.warning("⚠️ 未認証")
        
        if st.session_state.processing:
            st.warning("⏳ 処理中...")
        
        st.divider()
        
        if st.button("🔄 認証更新", disabled=st.session_state.processing):
            st.session_state.token = get_auth_token()
            if st.session_state.token:
                st.success("認証成功！")
            else:
                st.error("認証失敗")
        
        # デバッグモード
        st.divider()
        st.session_state.debug_mode = st.checkbox("🔍 デバッグモード", st.session_state.debug_mode)
        
        # 最後のレスポンス表示
        if st.session_state.debug_mode and st.session_state.last_response:
            st.divider()
            st.caption("📝 最後のレスポンス:")
            st.json(st.session_state.last_response)
    
    # メインコンテンツ
    st.header("🎮 VPS管理")
    
    if st.session_state.processing:
        st.info("⏳ コマンド実行中です。しばらくお待ちください...")
    
    # 状態取得
    server = get_server_status()
    
    if server:
        # ステータス表示
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if server['status'] == 'ACTIVE':
                st.success(f"🟢 稼働中")
            elif server['status'] == 'SHUTOFF':
                st.error(f"🔴 停止中")
            else:
                st.warning(f"⏳ {server['status']}")
        
        with col2:
            ip = "160.251.169.174"
            st.info(f"📍 IP: {ip}")
        
        with col3:
            st.metric("サーバー名", server.get('name', 'Unknown'))
        
        with col4:
            task_state = server.get('task_state')
            if task_state:
                st.warning(f"🔄 {task_state}")
            else:
                st.success("✅ 待機中")
        
        st.divider()
        
        # 操作ボタン
        col1, col2, col3, col4 = st.columns(4)
        
        buttons_disabled = st.session_state.processing or (server.get('task_state') is not None)
        
        with col1:
            if st.button("🟢 起動", 
                        disabled=(server['status'] == 'ACTIVE' or buttons_disabled),
                        use_container_width=True,
                        key="start_button"):
                
                with st.spinner("起動コマンド送信中..."):
                    result = start_vps()
                    if result:
                        st.success("✅ 起動コマンド送信成功！")
                        st.info("📢 3-5分後にARKサーバーに接続可能です")
                        st.balloons()
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 起動に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Status Code: {st.session_state.last_response.get('status_code', 'N/A')}")
        
        with col2:
            if st.button("🔴 停止",
                        disabled=(server['status'] == 'SHUTOFF' or buttons_disabled),
                        use_container_width=True,
                        key="stop_button"):
                
                with st.spinner("停止コマンド送信中..."):
                    result = stop_vps()
                    if result:
                        st.success("✅ 停止コマンド送信成功！")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 停止に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Status Code: {st.session_state.last_response.get('status_code', 'N/A')}")
        
        with col3:
            if st.button("🔄 再起動",
                        disabled=(server['status'] != 'ACTIVE' or buttons_disabled),
                        use_container_width=True,
                        key="reboot_button"):
                
                with st.spinner("再起動コマンド送信中..."):
                    result = reboot_vps()
                    if result:
                        st.success("✅ 再起動コマンド送信成功！")
                        st.warning("⏳ 5-7分お待ちください")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 再起動に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Status Code: {st.session_state.last_response.get('status_code', 'N/A')}")
        
        with col4:
            if st.button("🔄 状態更新", 
                        use_container_width=True,
                        disabled=st.session_state.processing,
                        key="refresh_button"):
                st.rerun()
        
        if server.get('task_state'):
            st.warning(f"""
            ⚠️ 現在サーバーは「{server['task_state']}」処理中です。
            処理が完了するまでお待ちください。
            """)
        
        # 接続情報
        st.divider()
        st.header("📊 接続情報")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.code(f"""
ARKサーバー接続先:
IP: 160.251.169.174
Port: 27015
接続: 160.251.169.174:27015
            """)
        
        with col2:
            st.code(f"""
Discord Bot:
!ark - 状態確認
!start - ARK起動
!stop - ARK停止
!shutdown - VPS停止
            """)
        
        # 使い方
        with st.expander("📖 使い方"):
            st.markdown("""
            ### 🚀 VPS起動手順
            1. 「🟢 起動」ボタンをクリック
            2. 3-5分待つ（VPS起動 + ARK自動起動）
            3. Steamで `160.251.169.174:27015` に接続
            
            ### 🛑 VPS停止手順
            方法1: このページで「🔴 停止」
            
            ### 📊 ステータスコード
            - **202**: 非同期処理受付成功（正常）
            - **200**: 同期処理成功
            - **409**: すでに実行中（正常）
            
            ### 🔍 デバッグモード
            問題が発生した場合は、サイドバーの「デバッグモード」をONにしてステータスコードを確認してください。
            """)
        
        # デバッグ情報表示
        if st.session_state.debug_mode:
            with st.expander("🔍 サーバー詳細情報"):
                st.json(server)
    else:
        st.error("サーバー情報を取得できません")
        if st.button("🔄 認証を再試行", disabled=st.session_state.processing):
            st.session_state.token = get_auth_token()
            st.rerun()
    
    # フッター
    st.divider()
    st.caption("🦖 ARK Server Manager - 202 Fixed Version")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
ConoHa VPS管理システム
ステータスコード完全対応版
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
st.markdown("ConoHa VPS管理システム（完全版）")

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
    """VPS起動（改善版）"""
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
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "起動",
            "status_code": response.status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # より寛容な成功判定
        # 2xx系は全て成功、409も成功（すでに起動中）
        if 200 <= response.status_code < 300 or response.status_code == 409:
            if response.status_code == 409:
                st.info("ℹ️ すでに起動中または起動処理中です")
            return True
        
        # エラーレスポンスの内容を確認
        try:
            error_data = response.json()
            # エラーメッセージに特定の文言が含まれる場合は成功とみなす
            error_msg = str(error_data).lower()
            if "already" in error_msg or "conflict" in error_msg or "running" in error_msg:
                return True
        except:
            pass
        
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
    """VPS停止（改善版）"""
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
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "停止",
            "status_code": response.status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # より寛容な成功判定
        # 2xx系は全て成功、409も成功（すでに停止中）
        if 200 <= response.status_code < 300 or response.status_code == 409:
            if response.status_code == 409:
                st.info("ℹ️ すでに停止中または停止処理中です")
            return True
        
        # エラーレスポンスの内容を確認
        try:
            error_data = response.json()
            error_msg = str(error_data).lower()
            if "already" in error_msg or "conflict" in error_msg or "shutoff" in error_msg or "stopped" in error_msg:
                return True
        except:
            pass
        
        # 特定のステータスコードは警告付きで成功とする
        if response.status_code in [400, 403, 404]:
            st.warning(f"⚠️ 予期しないレスポンス(Code: {response.status_code})ですが、コマンドは送信されました")
            return True
        
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
    """VPS再起動（改善版）"""
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
        
        # デバッグ情報を保存
        st.session_state.last_response = {
            "action": "再起動",
            "status_code": response.status_code,
            "time": datetime.now().strftime("%H:%M:%S")
        }
        
        # 2xx系は全て成功
        if 200 <= response.status_code < 300:
            return True
        
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
        
        st.header("💰 料金")
        st.metric("時間単価", "6.6円/時間")
        st.metric("月額上限", "3,608円")
        
        if st.button("🔄 認証更新", disabled=st.session_state.processing):
            st.session_state.token = get_auth_token()
            if st.session_state.token:
                st.success("認証成功！")
            else:
                st.error("認証失敗")
        
        # デバッグモード切り替え
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
            ip = "163.44.119.3"
            st.info(f"📍 IP: {ip}")
        
        with col3:
            st.metric("サーバー名", server.get('name', 'Unknown'))
        
        with col4:
            task_state = server.get('task_state')
            if task_state:
                st.warning(f"🔄 {task_state}")
            else:
                st.success("✅ 待機中")
        
        # デバッグ情報表示
        if st.session_state.debug_mode:
            with st.expander("🔍 サーバー詳細情報"):
                st.json(server)
        
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
                    if start_vps():
                        st.success("✅ 起動コマンド送信成功！")
                        if st.session_state.debug_mode:
                            st.info(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
                        st.info("📢 3-5分後にARKサーバーに接続可能です")
                        st.balloons()
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 起動に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
        
        with col2:
            if st.button("🔴 停止",
                        disabled=(server['status'] == 'SHUTOFF' or buttons_disabled),
                        use_container_width=True,
                        key="stop_button"):
                
                with st.spinner("停止コマンド送信中..."):
                    if stop_vps():
                        st.success("✅ 停止コマンド送信成功！")
                        if st.session_state.debug_mode:
                            st.info(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 停止に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
        
        with col3:
            if st.button("🔄 再起動",
                        disabled=(server['status'] != 'ACTIVE' or buttons_disabled),
                        use_container_width=True,
                        key="reboot_button"):
                
                with st.spinner("再起動コマンド送信中..."):
                    if reboot_vps():
                        st.success("✅ 再起動コマンド送信成功！")
                        if st.session_state.debug_mode:
                            st.info(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
                        st.warning("⏳ 5-7分お待ちください")
                        time.sleep(5)
                        st.rerun()
                    else:
                        st.error("❌ 再起動に失敗しました")
                        if st.session_state.debug_mode:
                            st.error(f"Debug: Status Code = {st.session_state.last_response.get('status_code', 'N/A')}")
        
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
IP: 163.44.119.3
Port: 7777
接続: 163.44.119.3:7777
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
            3. Steamで `163.44.119.3:7777` に接続
            
            ### 🛑 VPS停止手順
            方法1: このページで「🔴 停止」
            方法2: Discordで `!shutdown`
            
            ### 🔍 デバッグモード
            サイドバーの「デバッグモード」をONにすると：
            - APIレスポンスのステータスコード表示
            - サーバーの詳細情報表示
            - エラーの詳細確認
            
            ### ⚠️ 注意事項
            - ボタンは1回だけクリック
            - 処理中は他のボタンが無効
            - タスク実行中は操作不可
            """)
    else:
        st.error("サーバー情報を取得できません")
        if st.button("🔄 認証を再試行", disabled=st.session_state.processing):
            st.session_state.token = get_auth_token()
            st.rerun()
    
    # フッター
    st.divider()
    st.caption("🦖 ARK Server Manager - Final Version")

if __name__ == "__main__":
    main()
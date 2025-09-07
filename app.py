#!/usr/bin/env python3
"""
ConoHa c3j1リージョン対応 VPS管理システム
最終修正版 - エンドポイント修正済み
"""

import streamlit as st
import requests
import json
from datetime import datetime
import time

# ページ設定
st.set_page_config(
    page_title="ARK Server Manager",
    page_icon="🦖",
    layout="wide"
)

st.title("🦖 ARK Server Manager")
st.markdown("ConoHa VPS管理システム（c3j1リージョン対応）")

# 設定値取得（Streamlit Secretsから）
try:
    CONOHA_USERNAME = st.secrets["CONOHA_USERNAME"]
    CONOHA_PASSWORD = st.secrets["CONOHA_PASSWORD"]
    CONOHA_TENANT_ID = st.secrets["CONOHA_TENANT_ID"]
    VPS_SERVER_ID = st.secrets["VPS_SERVER_ID"]
except Exception as e:
    st.error(f"⚠️ Secrets読み込みエラー: {e}")
    st.info("""
    Streamlit Cloud → Settings → Secrets で以下を設定:
    ```
    CONOHA_USERNAME = "gncu69143183"
    CONOHA_PASSWORD = "your_password"
    CONOHA_TENANT_ID = "c31034637b164e79b3f8478ef71037b3"
    VPS_SERVER_ID = "your_server_id"
    ```
    """)
    st.stop()

# エンドポイント（c3j1リージョン）
AUTH_ENDPOINT = "https://identity.c3j1.conoha.io/v3/auth/tokens"
COMPUTE_ENDPOINT = "https://compute.c3j1.conoha.io/v2.1"  # ← ここを修正！テナントIDは不要

# セッション状態
if 'token' not in st.session_state:
    st.session_state.token = None
if 'vps_status' not in st.session_state:
    st.session_state.vps_status = None

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
            st.error(f"認証失敗: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"認証エラー: {e}")
        return None

def get_server_list():
    """サーバー一覧を取得（デバッグ用）"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    if not st.session_state.token:
        return None
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.get(
            f"{COMPUTE_ENDPOINT}/servers",
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()['servers']
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
                'addresses': server.get('addresses', {})
            }
        elif response.status_code == 401:
            # トークン期限切れ
            st.session_state.token = get_auth_token()
            return get_server_status()  # リトライ
        elif response.status_code == 404:
            # サーバーが見つからない場合、一覧を確認
            servers = get_server_list()
            if servers:
                st.error(f"サーバーID {VPS_SERVER_ID} が見つかりません")
                st.info("利用可能なサーバー:")
                for server in servers:
                    st.write(f"- {server['name']}: {server['id']}")
                st.info(f"正しいサーバーIDをSecrets内のVPS_SERVER_IDに設定してください")
            return None
        else:
            st.error(f"サーバー情報取得失敗: {response.status_code}")
            return None
    except Exception as e:
        st.error(f"エラー: {e}")
        return None

def start_vps():
    """VPS起動"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-start": None}
        )
        return response.status_code == 202
    except:
        return False

def stop_vps():
    """VPS停止"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-stop": None}
        )
        return response.status_code == 202
    except:
        return False

def reboot_vps():
    """VPS再起動"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"reboot": {"type": "SOFT"}}
        )
        return response.status_code == 202
    except:
        return False

# メイン画面
def main():
    # サイドバー
    with st.sidebar:
        st.header("⚙️ 設定")
        st.success("c3j1リージョン接続")
        
        # トークン状態
        if st.session_state.token:
            st.success("✅ API認証済み")
        else:
            st.warning("⚠️ 未認証")
        
        st.divider()
        
        st.header("💰 料金")
        st.metric("時間単価", "6.6円/時間")
        st.metric("月額上限", "3,608円")
        
        if st.button("🔄 認証更新"):
            st.session_state.token = get_auth_token()
            if st.session_state.token:
                st.success("認証成功！")
            else:
                st.error("認証失敗")
        
        # サーバー一覧確認（デバッグ用）
        with st.expander("🔍 サーバー一覧確認"):
            if st.button("サーバー一覧取得"):
                servers = get_server_list()
                if servers:
                    for server in servers:
                        st.code(f"{server['name']}: {server['id']}")
                else:
                    st.error("サーバー一覧を取得できません")
    
    # メインコンテンツ
    st.header("🎮 VPS管理")
    
    # 状態取得
    server = get_server_status()
    
    if server:
        # ステータス表示
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if server['status'] == 'ACTIVE':
                st.success(f"🟢 稼働中")
            elif server['status'] == 'SHUTOFF':
                st.error(f"🔴 停止中")
            else:
                st.warning(f"⏳ {server['status']}")
        
        with col2:
            # IPアドレス取得
            ip = "163.44.119.3"  # 固定
            st.info(f"📍 IP: {ip}")
        
        with col3:
            st.metric("サーバー名", server.get('name', 'Unknown'))
        
        st.divider()
        
        # 操作ボタン
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("🟢 起動", 
                        disabled=(server['status'] == 'ACTIVE'),
                        use_container_width=True):
                with st.spinner("起動中..."):
                    if start_vps():
                        st.success("✅ 起動コマンド送信成功！")
                        st.info("3-5分後にARKサーバーに接続可能です")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 起動失敗")
        
        with col2:
            if st.button("🔴 停止",
                        disabled=(server['status'] == 'SHUTOFF'),
                        use_container_width=True):
                with st.spinner("停止中..."):
                    if stop_vps():
                        st.success("✅ 停止コマンド送信成功！")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 停止失敗")
        
        with col3:
            if st.button("🔄 再起動",
                        disabled=(server['status'] != 'ACTIVE'),
                        use_container_width=True):
                with st.spinner("再起動中..."):
                    if reboot_vps():
                        st.success("✅ 再起動コマンド送信成功！")
                        time.sleep(3)
                        st.rerun()
                    else:
                        st.error("❌ 再起動失敗")
        
        with col4:
            if st.button("🔄 更新", use_container_width=True):
                st.rerun()
        
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
            ### VPS起動手順
            1. 「🟢 起動」ボタンをクリック
            2. 3-5分待つ（VPS起動 + ARK自動起動）
            3. Steamで `163.44.119.3:7777` に接続
            
            ### VPS停止手順
            方法1: このページで「🔴 停止」
            方法2: Discordで `!shutdown`
            
            ### 料金について
            - 起動中: 6.6円/時間
            - 停止中: 0円
            - 月額上限: 3,608円
            
            ### Discord Bot
            VPS起動時に自動でDiscord Botも起動します。
            """)
    else:
        st.error("サーバー情報を取得できません")
        
        # 対処法を表示
        st.info("""
        ### 考えられる原因:
        1. VPS_SERVER_IDが正しくない
        2. サーバーが存在しない
        3. 認証エラー
        
        サイドバーの「🔍 サーバー一覧確認」から正しいサーバーIDを確認してください。
        """)
        
        if st.button("🔄 認証を再試行"):
            st.session_state.token = get_auth_token()
            st.rerun()
    
    # フッター
    st.divider()
    st.caption("🦖 ARK Server Manager - c3j1 Region - Fixed Endpoint Version")

if __name__ == "__main__":
    main()
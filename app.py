#!/usr/bin/env python3
"""
ConoHa VPS管理システム
アクションコマンドのステータスコード修正版
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
st.markdown("ConoHa VPS管理システム（アクション修正版）")

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

# セッション状態
if 'token' not in st.session_state:
    st.session_state.token = None
if 'vps_status' not in st.session_state:
    st.session_state.vps_status = None
if 'action_log' not in st.session_state:
    st.session_state.action_log = []

def log_action(action, status_code, success):
    """アクションログを記録"""
    log_entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "action": action,
        "status_code": status_code,
        "success": success
    }
    st.session_state.action_log.append(log_entry)
    # 最新10件のみ保持
    st.session_state.action_log = st.session_state.action_log[-10:]

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
                'addresses': server.get('addresses', {})
            }
        elif response.status_code == 401:
            st.session_state.token = get_auth_token()
            return get_server_status()
        else:
            return None
    except:
        return None

def start_vps():
    """VPS起動（修正版）"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-start": None}
        )
        
        # ステータスコードをログに記録
        success = response.status_code in [200, 202, 204]
        log_action("起動", response.status_code, success)
        
        # 409 Conflict = すでに起動している
        if response.status_code == 409:
            st.warning("すでに起動しています")
            return True
        
        return success
        
    except Exception as e:
        log_action("起動", "Error", False)
        return False

def stop_vps():
    """VPS停止（修正版）"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"os-stop": None}
        )
        
        # ステータスコードをログに記録
        success = response.status_code in [200, 202, 204]
        log_action("停止", response.status_code, success)
        
        # 409 Conflict = すでに停止している
        if response.status_code == 409:
            st.warning("すでに停止しています")
            return True
        
        # 停止コマンドは202以外でも成功の可能性がある
        # ConoHa APIの仕様によっては200や204を返すこともある
        return success or response.status_code == 200
        
    except Exception as e:
        log_action("停止", "Error", False)
        return False

def reboot_vps():
    """VPS再起動（修正版）"""
    if not st.session_state.token:
        st.session_state.token = get_auth_token()
    
    headers = {"X-Auth-Token": st.session_state.token}
    
    try:
        response = requests.post(
            f"{COMPUTE_ENDPOINT}/servers/{VPS_SERVER_ID}/action",
            headers=headers,
            json={"reboot": {"type": "SOFT"}}
        )
        
        # ステータスコードをログに記録
        success = response.status_code in [200, 202, 204]
        log_action("再起動", response.status_code, success)
        
        return success
        
    except Exception as e:
        log_action("再起動", "Error", False)
        return False

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
        
        # アクションログ表示
        st.divider()
        st.header("📝 アクションログ")
        if st.session_state.action_log:
            for log in reversed(st.session_state.action_log[-5:]):
                if log['success']:
                    st.success(f"{log['time']} {log['action']} [{log['status_code']}]")
                else:
                    st.error(f"{log['time']} {log['action']} [{log['status_code']}]")
        else:
            st.caption("ログなし")
    
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
            ip = "163.44.119.3"
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
                        # エラーでもステータスを再確認
                        st.warning("⚠️ コマンド送信済み。状態を確認してください。")
                        time.sleep(2)
                        st.rerun()
        
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
                        # エラーでもステータスを再確認
                        st.warning("⚠️ コマンド送信済み。状態を確認してください。")
                        time.sleep(2)
                        st.rerun()
        
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
        
        # デバッグ情報（展開可能）
        with st.expander("🔍 デバッグ情報"):
            st.caption("最新のアクションログ:")
            if st.session_state.action_log:
                for log in reversed(st.session_state.action_log):
                    st.code(f"{log['time']} - {log['action']}: Status {log['status_code']} - Success: {log['success']}")
            
            st.caption("現在のサーバー状態:")
            st.json(server)
        
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
            
            ### トラブルシューティング
            - 停止が「失敗」と表示されても実際には成功していることがあります
            - その場合は「🔄 更新」で状態を確認してください
            """)
    else:
        st.error("サーバー情報を取得できません")
        if st.button("🔄 認証を再試行"):
            st.session_state.token = get_auth_token()
            st.rerun()
    
    # フッター
    st.divider()
    st.caption("🦖 ARK Server Manager - Action Fixed Version")

if __name__ == "__main__":
    main()